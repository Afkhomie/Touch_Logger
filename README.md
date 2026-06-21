# Touch Logger

Touch Logger is a multi-touch recording and macro playback application for Android devices. It allows users to record touch gestures, taps, and swipes on their mobile device and replay them automatically.

## Features

- Record touch gestures including taps, swipes, and multi-touch actions
- Playback recorded macros with adjustable speed and scaling
- Visual gesture map for real-time feedback
- Device caching for faster reconnection
- Dark mode support
- Profile management
- Analytics and plugin support

## Prerequisites

- Windows PC
- Android device with USB debugging enabled
- ADB (Android Debug Bridge) installed

## Installation

### ADB Setup

1. Download ADB platform tools from: https://dl.google.com/android/repository/platform-tools-latest-windows.zip
2. Extract the downloaded file
3. Navigate to the extracted folder: Downloads\platform-tools-latest-windows\platform-tools
4. Copy adb.exe from that folder
5. Paste adb.exe in the touch_logger folder alongside the main.exe file

### Phone Setup

1. Connect your Android device to your PC using a data cable
2. On your phone, go to Settings
3. Navigate to About Phone
4. Tap on Build Number 7 times to enable Developer Options
5. Go back to Settings and open Developer Options
6. Enable USB Debugging
7. Allow your PC to access the device when prompted

## Usage

### Connecting to Device

1. Run main.exe
2. Click the refresh icon next to the connect button
3. Click the connect button to establish connection with your mobile device
4. Once connected, perform movements on your mobile device (taps, swipes)
5. The movements should be visible on the virtual gesture map

### Recording Gestures

1. Ensure your phone is connected to the program
2. Press F9 or click the record button to start recording
3. Perform the desired movements on your device (taps, swipes, opening/closing apps, clearing recent apps, etc.)
4. Press F9 again or click the stop button to stop recording

### Saving Macros

1. After recording, click the save button located to the right of the clear button
2. Provide a name for your macro
3. Description and other fields are optional
4. Click save to store the macro

### Playback

1. Go to the playback section
2. Select the macro you saved earlier
3. Configure playback options:
   - Scale: Enable scaling to loop the automation
   - Speed: Adjust playback speed as needed
4. Press F11 or click the play button
5. Wait for the playback to start (this may take some time)
6. The recorded actions will be repeated automatically
7. Do not touch your mobile screen during playback

## Hotkeys

- F9: Start/Stop recording
- F10: Stop recording
- F11: Play macro
- F12: Toggle theme

## Troubleshooting

If you encounter any issues, bugs, or glitches during usage, please report them for further assistance.

## License

This project is provided as-is for testing and personal use.
