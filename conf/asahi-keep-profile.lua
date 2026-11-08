-- SPDX-License-Identifier: MIT
--
-- Keep a device on its profile when none of its ports is available.
--
-- WirePlumber selects only profiles that are available (or of unknown
-- availability), else "off". With speakerguardd v2 the built-in card's
-- HiFi profile has no Speaker port (UCM), only the headphone jack's: with
-- nothing plugged in, it is unavailable and the card would be turned off.
-- Its verb sets the speaker front-end's mux, and asahi-unplugged-routes.lua
-- needs the unplugged headphone node to keep its volume and mute.
--
-- For devices that set asahi.profile.keep = "<profile>", select that
-- profile whatever its availability, unless a stored or preferred profile
-- was found first.

cutils = require ("common-utils")
log = Log.open_topic ("s-device")

SimpleEventHook {
  name = "device/asahi-keep-profile",
  after = "device/find-preferred-profile",
  before = "device/find-best-profile",
  interests = {
    EventInterest {
      Constraint { "event.type", "=", "select-profile" },
      Constraint { "asahi.profile.keep", "is-present" },
    },
  },
  execute = function (event)
    if event:get_data ("selected-profile") then
      return
    end
    local device = event:get_subject ()
    local want = device.properties ["asahi.profile.keep"]
    for p in device:iterate_params ("EnumProfile") do
      local profile = cutils.parseParam (p, "EnumProfile")
      if profile and profile.name == want then
        log:info (device, "keeping profile " .. want .. " (available: " ..
            tostring (profile.available) .. ")")
        event:set_data ("selected-profile", profile)
        return
      end
    end
  end
}:register ()
