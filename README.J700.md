# MacBook Neo J700 — speakers, headphones and microphones

This addition needs the matching J700 UCM entries from alsa-ucm-conf-asahi.
It is built from upstream f5b118a8a2fb150b145cb667b4738cdab0304eb0.

The J700 is set up like the other Asahi laptops. Users see these devices:

| Device | Node | Available |
|---|---|---|
| "MacBook Neo J700 Speakers" | `audio_effect.j700-convolver` (DSP sink) | always |
| "Built-in Audio Headphones" | UCM `Headphones` on `hw:AppleJ700,0` | while headphones are plugged in |
| "MacBook Neo J700 Microphone" | `effect_output.j700-mic` (DSP source) | always; the default microphone |
| "Built-in Audio Headset Microphone" | UCM `Headset` on `hw:AppleJ700,0` | while a headset is plugged in |

The raw speaker and microphone-array nodes are hidden behind their DSP
filters, the same way as on the other machines. The J700 rules are part of
`conf/wireplumber.conf`; there is no separate J700 configuration file.

## Speakers

`hw:AppleJ700,1` is the raw speaker device (one MAX98360A per channel on the
AOP's LEAP serializer, S32LE at 48 kHz only).  As on every other Mac the
generic rule renames it `alsa_output.platform-sound.RawSpeakers` and the
`node.software-dsp` rule wraps it in `firs/j700/graph.json`, which is the
user-visible "MacBook Neo J700 Speakers" sink.  The graph has the usual shape
(bankstown bass extension, the LSP loudness compensator carrying the sink
volume as a flat gain (its contour set to Flat, so every band follows the
volume equally), a convolver per channel, the woofer band compressor and the final
limiter).  `firs/j700/48.wav` is a first correction measured on the
machine: an exponential sine sweep (100 Hz - 7.5 kHz, -50 dBFS on the wire)
recorded by the internal low-power microphone and deconvolved; only the
broad presence peaks (1.6 kHz, 2.5-3.2 kHz) and the mild rise above 5 kHz
are corrected, by a few dB, as a minimum-phase 2048-tap IR.  The internal
microphone is not a listener position, so this is deliberately gentle and
should be replaced by a measurement in front of the laptop; the
bankstown/compressor settings are provisional for the same reason.  The
graph only lists 48 kHz because the hardware path is fixed at that rate.

The raw device reaches the amplifier's full scale (0 dBFS on the wire,
7.3 V peak) only while a speaker-protection daemon (speakerguardd) holds
the card's volume lock and governs "Speaker Playback Volume" with its
thermal model; without the daemon the kernel holds that control 20 dB
down.  The control is not a PipeWire route volume and is never touched by
this configuration.

At 100 % the graph alone takes, measured on the machine (a -20 dBFS tone
recorded at the graph's output, 2026-10-15): -1.5 dB at 1 kHz, -6.6 dB at
2.5 kHz and -4.4 dB at 5 kHz, mostly the correction's cut of the
presence peaks.  The convolvers therefore carry +3 dB of make-up gain
(`"gain": 1.41`), as on j413.  The compressor that ends the shared graph
shape (`woofer_lim`, 0 dBFS, 15:1, RMS detection) lets transients through:
with the make-up gain, a mastered-music-like test signal (-1 dBFS peak,
12 dB crest factor) left the graph at up to +3.5 dBFS, and the S32
conversion clipped 0.06 % of its samples (18 clip events a second).  A
brick-wall limiter (LSP limiter, -0.5 dBFS, 5 ms lookahead) after it
removes those overs (0 clipped samples) without costing level.  Measured
with the internal microphone, the result is 2.75 dB louder at 100 % than
without the make-up gain, with the same frequency response; speakerguardd
took no reduction during 60 s of the test signal at 100 % (0.84 W mean
per speaker).

The speaker sink comes back at the volume and mute state it last had,
every time it is created (at every boot and whenever WirePlumber
restarts).  The limits that protect the speakers are the kernel ceiling
and the speaker-protection daemon above, not the sink volume.
`asahi-restore-volume.lua` stores and restores the sink's channel volumes
and mute state in place of WirePlumber's stream state, which the graph
turns off for this sink with `state.restore-props = false` and hands over
with `asahi.restore-props = true`.  The first time, the sink gets the
volume and mute WirePlumber had stored for it.  With nothing stored, or a
stored volume that is not a number from 0 to 1 for each channel, it gets
`state.default-volume`, 0.027: 30 % on desktop volume sliders (cubic
scale), audible for a first notification without starting loud.

The script logs every change of the sink's volume or mute state to the
journal, one notice line per burst of changes (WirePlumber's default log
level shows notices), for example:

    audio_effect.j700-convolver: volume 0.10 -> 1.00, mute false -> false (1 change; another client; clients connected just before: wpctl (pid 4242); peak volume 1.00)

Volumes are shown as desktop sliders show them.  PipeWire does not say
which client set a parameter, so the line says whether the script's own
restore made the change and otherwise lists the PipeWire clients that
connected in the three seconds before it.  That names one-shot tools,
including PulseAudio clients such as `pactl`, which pipewire-pulse
connects as clients of their own.  A change made through a client that was
already connected, such as the desktop shell, shows no new client; the
time of the line then has to be matched against that client's own logs.

The change log keeps external bursts even when the volume and mute finish
where they started, and reports the peak volume reached during each burst.
A burst containing both a restore and an external change names both; only
an unchanged burst entirely due to restore is omitted.

## Measuring distortion

`tools/sweep-hd.py` generates a log sweep per speaker and turns a
recording of it into each speaker's SNR, 2nd to 5th harmonic distortion and
octave-band SNR.  A harmonic that is less than 6 dB above the noise floor of
the same impulse response is reported as "< floor": at the quiet levels a
laptop measurement uses, that is the usual result, and the highest sample of
a harmonic window is then only the noise floor.

Comparing two capture chains (macOS against Linux, or the raw array
`hw:AppleJ700AOP,1` against the microphone filter) needs the same acoustic
level, which the band SNR shows independently of capture gain; the
microphone filter alone adds +36 dB.  The sink volume is not a level: at
35 % the graph was -29 dB at 1 kHz and -33 dB from 1.6 to 4 kHz (the
ISO 226 loudness contour it then had), and at 63 % about -16 dB.  With the
flat contour every band takes the same -30.9 dB at 35 % (the slider maps
linearly onto -47.5..0 dB).

Measured 2026-11-05 at one placement with the array as the microphone and
the same sweep at -20 dBFS: at sink volume 35 % Linux gave SNR 42/40 dB and
"HD" -29 to -34 dB, the floor of a quiet recording, the same through the
raw array and through the filter.  At a level 11 to 20 dB higher at the
microphone, sink volume 63 %, it gives SNR 55/54 dB, HD2 -45/-45 dB and
HD3 -46/-45 dB, again the floor; the speaker PCM fed directly at -36 dBFS
gives 54/54, -45/-45 and -45/-44 dB.  The graph's own output, rendered
offline at 35 %, 63 % and 100 %, carries harmonics below -76 dB.

## Headphones and headset microphone

The 3.5 mm jack is a CS42L83 on `hw:AppleJ700,0`, described by the shared
laptop UCM verb, so the nodes, names and priorities are the stock ones.
The jack uses ALSA S24_LE (PipeWire S24_32LE) at 48 kHz: stereo output and
mono headset input.  The jack-detect controls make both routes available
only while something is plugged in.

The J700-specific part is the initial headphone volume: 0.001, or -60 dB
relative to jack full scale, which desktop volume sliders (cubic scale)
show as 10 %.  It is set with `device.routes.default-sink-volume` on the
card device.  A volume the user has already set takes precedence, and
there is no ceiling.

WirePlumber only selects routes that are available, so with nothing in
the jack the headphone node would get no route and report 100 % until
something is plugged in.  `asahi-unplugged-routes.lua`, enabled for the
built-in card of every Mac with `asahi.routes.select-unplugged`, selects
the unplugged headphone route anyway, so the node always shows the volume
the headphones will get: the stored one, or the default above.
WirePlumber does not store what is set on an unavailable route, so the
script also keeps the volume and mute set while nothing is plugged in
(`~/.local/state/wireplumber/asahi-unplugged-routes`) and applies them
whenever the route is selected, until they are changed again with
headphones in.

## Microphones

The microphones are on a second, capture-only card, `AppleJ700AOP` (driver
`t8140-aop-audio`, long name "MacBook Neo J700 AOP Audio"), not on macaudio.

**The microphone array** is PCM 1, `hpai`: two capsules, float32 (PipeWire
F32LE) at 48 kHz only.  It is the card's only UCM device ("Mic").  Like the
`AppleJxxxHPAI` cards of the other laptops, it is renamed
`alsa_input.platform-sound.RawMics`, hidden, and wrapped by the
`node.software-dsp` rule in `firs/j700/mic.json`.  The result is the
"MacBook Neo J700 Microphone" source, at the same priority as the other
machines' microphones.  The filter averages the two capsules, adds +36 dB of
make-up gain in two x8 stages and applies the usual 120 Hz high-pass.  There is
no beamformer for a two-capsule array, and the gain is provisional until it
is calibrated against the other machines.

**The low-power microphone** is PCM 0, `lpai`.  It is not a user device:
it is absent from the UCM verb, and a WirePlumber rule disables any node on
PCM 0 of `AppleJ700AOP`, so no profile of the card (not even pro-audio) shows it.
It exists for developers working on always-on, low-power features such as
wake-word detection.

* ALSA device `hw:AppleJ700AOP,0`, capture only: S32_LE, 16 kHz, two
  channels, in fixed 200 ms periods (3200 frames, a buffer of two to four
  periods), for example:

      arecord -D hw:AppleJ700AOP,0 -f S32_LE -r 16000 -c 2 -d 5 lpmic.wav

* For a PipeWire source, link `firs/j700/lpmic-developer.conf` (installed as
  `/usr/share/asahi-audio/j700/lpmic-developer.conf`) into
  `~/.config/pipewire/pipewire.conf.d/` and restart `pipewire` and
  `wireplumber`; the file has the exact commands.  This adds "Aurora
  Low-Power Microphone (developer)" (`alsa_input.j700-lpmic-developer`) at
  priority 1, so it never becomes the default while the array exists.
  Remove the link to turn it off again.

A WirePlumber state that saved the `pro-audio` profile for the AOP card
bypasses UCM and with it the microphone filter.  Select the card's default
profile (HiFi) again to get the "MacBook Neo J700 Microphone" back.
