-- SPDX-License-Identifier: MIT
--
-- Hide a sound card's device from clients.
--
-- software-dsp's hide-parent hides the raw node it puts a filter in front
-- of, but not the card the node belongs to. Desktops (GNOME, KDE, anything
-- on the PulseAudio API) build their device lists from the cards' ports as
-- well as from the sinks and sources, so a card whose only node is hidden
-- still shows its port: a second, dead "Microphone" beside the filter's
-- source, or a "Speakers" port beside speakerguardd v2's voicing sink.
--
-- For devices that set asahi.hide-device = true, take every permission on
-- the device away from every client but WirePlumber, as software-dsp does
-- for the node. WirePlumber keeps managing the device (its profile, routes
-- and nodes); clients see neither it nor its ports.

cutils = require ("common-utils")
log = Log.open_topic ("s-device")

clients_om = ObjectManager {
  Interest { type = "client" }
}

devices_om = ObjectManager {
  Interest { type = "device" }
}

local function hidden (device)
  return cutils.parseBool (device.properties ["asahi.hide-device"])
end

local function hide (client, id)
  if not client.properties ["wireplumber.daemon"] then
    client:update_permissions { [id] = "-" }
  end
end

devices_om:connect ("object-added", function (_, device)
  if not hidden (device) then
    return
  end
  local id = device ["bound-id"]
  log:info ("hiding device " .. tostring (device.properties ["device.name"]) .. " (" .. id .. ") from clients")
  for client in clients_om:iterate () do
    hide (client, id)
  end
end)

clients_om:connect ("object-added", function (_, client)
  for device in devices_om:iterate () do
    if hidden (device) then
      hide (client, device ["bound-id"])
    end
  end
end)

clients_om:activate ()
devices_om:activate ()
