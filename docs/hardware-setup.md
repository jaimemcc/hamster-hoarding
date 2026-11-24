# Hardware setup: cameras, cables and hub

Planned USB layout and parts list. Check lengths and power before buying anything new.

## Cameras

| Item | Part number | Notes |
|---|---|---|
| USB camera (x2 for first test, up to 4 planned) | ELP-USBFHD01M-BL170IR | 1080p, USB 2.0, 170° IR-capable. Ships with a 3 m cable attached. |

## Cables

| Run | Cable | Length | Type | Notes |
|---|---|---|---|---|
| Camera to extension | Built-in camera cable | 3 m | Passive USB 2.0 | Supplied with camera. |
| Laptop to hub | StarTech 2m Black SuperSpeed USB 3.0 Extension Cable A to A (USB3SEXT2MBK) | 2 m | Passive (USB 3.0), male-to-female | Works for USB 2.0 cameras. Keep this run at 2 m or less. |
| Alternative, if the hub is further away | USB2AAEXT5M | 5 m | Active USB 2.0 repeater | Bus-powered, with optional wall power adapter. Use if the laptop-to-hub run needs to be longer than 2 m. |

Length rule for passive USB 2.0: total run from the camera's chip to the host port should stay under about 5 m. Passive USB 3.0 is limited to about 3 m. Anything longer needs an active extension (or USB-over-Ethernet for very long runs).

## Hub

| Item | Part number | Notes |
|---|---|---|
| 4-port powered USB 3.0 hub | StarTech ST4300USB3V2-UE | Power adapter confirmed included. Two cameras need a powered hub. |

## Planned topology (2-camera test)

```
Laptop --- 2 m USB 3.0 extension --- ST4300USB3V2 (powered) --- camera 1 (3 m cable)
                                                            --- camera 2 (3 m cable)
```

- Each camera run: 3 m (passive USB 2.0), within limits.
- Laptop to hub: 2 m (passive), within limits.
- Bandwidth: two 1080p cameras in MJPG share the hub's USB 2.0 bus (480 Mbps). Fine in MJPG; uncompressed 1080p will not fit.

## Scaling to 4 cameras

The project targets 4 cameras (see [TODO.md](../TODO.md)). Before adding the other two:
- Check USB bandwidth with all four on the same hub, or use a second hub on a different laptop port/controller.
- If the hub sits farther from the laptop, use the 5 m active extension (USB2AAEXT5M) for that run.
- Confirm the hub's power supply can run all cameras plus the hub.

## Open items

- [x] Confirm the ST4300USB3V2-UE box includes the power adapter (confirmed).
- [ ] Measure the actual laptop-to-hub distance before buying the active 5 m cable.
- [ ] Test two cameras on the hub, then decide on a second hub for the other two.
