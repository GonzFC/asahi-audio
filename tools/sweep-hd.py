#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Speaker frequency response and harmonic distortion from a log-sweep recording.

    sweep-hd.py gen OUT.wav [--level DBFS] [--speakers N] [--int32]
    sweep-hd.py analyse REC.wav [REC.wav ...] [--channel C] [--speakers N]

`gen` writes one exponential sine sweep per speaker (100 Hz to 16 kHz,
6 s, at --level dBFS peak), each on its own channel and one after the
other: 1 s of silence, speaker 1, 1 s gap, speaker 2, ..., 1 s of silence.
Play it through the path under test and record it with a microphone that
hears all speakers.  `analyse` deconvolves each recording (Farina's
method), which separates the linear impulse response of every speaker from
the impulse responses of its 2nd to 5th harmonics.

What it reports, per speaker:

* SNR: the linear impulse response's peak over the RMS of a stretch of the
  same response that holds no harmonic.
* HDn: the energy of the nth harmonic's impulse response relative to the
  linear one, next to the energy of the same window length taken where
  there is no harmonic (the floor).  A harmonic less than 6 dB above the
  floor is printed as "< floor": it was not measured, only bounded.
  Picking the highest sample of a harmonic window instead returns the
  noise floor whenever the recording is noisy; two recordings whose
  "distortion" differs then differ only in SNR.
* Band SNR: the linear response over the floor in octave bands.  It does
  not depend on the microphone's gain, so it is the way to match the
  acoustic level of two recordings made through different capture chains
  (for example two operating systems): equal band SNR in the bands where
  the room noise dominates means equal level at the microphone.  Peak
  impulse-response levels do not: they include the capture gain.

Every recording given to one run is analysed identically.  WAV files may
be 16/24/32-bit integer or 32-bit float, any number of channels.
"""
import argparse
import sys

import numpy
import scipy.io.wavfile
from scipy import signal

RATE = 48000
F1, F2, DUR, GAP, LEAD = 100.0, 16000.0, 6.0, 1.0, 1.0
K = DUR / numpy.log(F2 / F1)        # seconds per e-fold of frequency
BANDS = [(100, 200), (200, 400), (400, 800), (800, 1600), (1600, 3200), (3200, 6400), (6400, 12800)]
DETECT_DB = 6.0


def sweep():
    t = numpy.arange(int(DUR * RATE)) / RATE
    x = numpy.sin(2 * numpy.pi * F1 * K * (numpy.exp(t / K) - 1))
    fade = int(0.01 * RATE)
    x[:fade] *= numpy.linspace(0, 1, fade)
    x[-fade:] *= numpy.linspace(1, 0, fade)
    return x


def inverse():
    x = sweep()
    t = numpy.arange(len(x)) / RATE
    return x[::-1] * numpy.exp(-t / K)


def gen(args):
    s = sweep() * 10 ** (args.level / 20)
    n = args.speakers
    lead, step = int(LEAD * RATE), int((DUR + GAP) * RATE)
    out = numpy.zeros((lead * 2 + step * n - int(GAP * RATE), n))
    for k in range(n):
        out[lead + k * step:lead + k * step + len(s), k] = s
    if args.int32:
        data = numpy.round(out * 2 ** 31).clip(-2 ** 31, 2 ** 31 - 1).astype("<i4")
    else:
        data = numpy.round(out * 32767).astype("<i2")
    scipy.io.wavfile.write(args.out, RATE, data)


def read(path, channel):
    rate, d = scipy.io.wavfile.read(path)
    if rate != RATE:
        sys.exit("%s: %d Hz, expected %d" % (path, rate, RATE))
    if d.dtype.kind == "i":
        d = d.astype(float) / float(numpy.iinfo(d.dtype).max + 1)
    elif d.dtype.kind == "u":
        d = (d.astype(float) - 128) / 128
    d = d.astype(float)
    return d if d.ndim == 1 else d[:, min(channel, d.shape[1] - 1)]


def energy(h, c, w):
    return numpy.sum(h[c - w // 4:c + 3 * w // 4] ** 2)


def analyse_one(path, args, inv):
    y = read(path, args.channel)
    n = 1 << int(numpy.ceil(numpy.log2(len(y) + len(inv))))
    h = numpy.fft.irfft(numpy.fft.rfft(y, n) * numpy.fft.rfft(inv, n), n)
    env = numpy.abs(h)
    step = int((DUR + GAP) * RATE)
    # the speakers' linear responses are step apart; anchor on the strongest
    best = int(numpy.argmax(env))
    starts = [best - k * step for k in range(args.speakers)]
    def total(first):
        return sum(env[max(0, first + k * step - 50):first + k * step + 50].max()
                   for k in range(args.speakers) if 0 <= first + k * step < len(h) - 2048)
    first = max((s for s in starts if s - int(K * numpy.log(6) * RATE) > 0), key=total, default=best)
    w = int(0.010 * RATE)
    lo, hi = int(0.85 * K * numpy.log(2) * RATE), int(0.15 * K * numpy.log(2) * RATE)
    nfft, seg = 16384, 4096
    f = numpy.fft.rfftfreq(nfft, 1 / RATE)
    win = numpy.hanning(seg)
    print(path)
    for k in range(args.speakers):
        c = first + k * step
        i = c - 50 + int(numpy.argmax(env[c - 50:c + 50]))
        floor_w = [energy(h, j, w) for j in range(i - lo, i - hi, w)]
        floor = numpy.median(floor_w)
        lin = energy(h, i, w)
        noise_rms = numpy.sqrt(numpy.mean(h[i - lo:i - hi] ** 2))
        out = ["SNR %5.1f dB" % (20 * numpy.log10(env[i] / noise_rms)),
               "floor %6.1f dB" % (10 * numpy.log10(floor / lin))]
        for nh in (2, 3, 4, 5):
            j = i - int(round(K * numpy.log(nh) * RATE))
            j = j - w // 2 + int(numpy.argmax(env[j - w // 2:j + w // 2]))
            e = energy(h, j, w)
            if 10 * numpy.log10(e / floor) < DETECT_DB:
                out.append("HD%d < floor" % nh)
            else:
                out.append("HD%d %6.1f dB" % (nh, 10 * numpy.log10(e / lin)))
        print("  speaker %d: %s" % (k + 1, ", ".join(out)))
        sig = numpy.abs(numpy.fft.rfft(h[i - 512:i - 512 + seg] * win, nfft)) ** 2
        noise = numpy.mean([numpy.abs(numpy.fft.rfft(h[j:j + seg] * win, nfft)) ** 2
                            for j in range(i - lo, i - hi - seg, 1024)], axis=0)
        bands = []
        for b0, b1 in BANDS:
            m = (f >= b0) & (f < b1)
            bands.append("%d-%d %.0f" % (b0, b1, 10 * numpy.log10(sig[m].mean() / noise[m].mean())))
        print("    band SNR dB: " + ", ".join(bands))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("out")
    g.add_argument("--level", type=float, default=-20.0, help="sweep peak, dBFS (default -20)")
    g.add_argument("--speakers", type=int, default=2)
    g.add_argument("--int32", action="store_true", help="32-bit integer samples (default 16-bit)")
    a = sub.add_parser("analyse")
    a.add_argument("recordings", nargs="+")
    a.add_argument("--channel", type=int, default=0, help="recording channel to analyse (default 0)")
    a.add_argument("--speakers", type=int, default=2)
    args = p.parse_args()
    if args.cmd == "gen":
        gen(args)
    else:
        inv = inverse()
        for path in args.recordings:
            analyse_one(path, args, inv)


if __name__ == "__main__":
    main()
