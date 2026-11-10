Clear Context desktop app
=========================

Clear Context separates a post into claims, researches each detail and shows the
source passage every finding rests on. It runs on this computer and opens in your
browser. Source code, documentation and known limitations:
https://github.com/uslanozan/Clear-Context


Start it
--------
Windows: open the "Clear Context" folder and double-click "Clear Context.exe".
macOS:   open the "Clear Context" folder and double-click "Clear Context".
Linux:   open a terminal in the "Clear Context" folder and run ./"Clear Context"

A window shows the address (normally http://127.0.0.1:8765/) and your browser opens
it. Keep that window open while you use Clear Context; closing it stops the app.
Starting it again while it runs just opens the browser.


The first start may show a warning
----------------------------------
The app is not signed, so the system cannot name its publisher.

Windows: if "Windows protected your PC" appears, choose "More info", then "Run anyway".
macOS:   if the app "cannot be opened", open System Settings > Privacy & Security,
         find the message about Clear Context and choose "Open Anyway". Or, in
         Terminal, remove the download quarantine from the folder:
         xattr -dr com.apple.quarantine "/path/to/Clear Context"


Before your first investigation
-------------------------------
Until you add keys, the app runs in preview mode and researches nothing.
In the app, open Settings:
1. Add a Meta API key (https://dev.meta.ai/). Tavily, SerpApi and Google Fact Check
   keys are optional; each field links to the page where its key is created.
2. Turn on "Allow paid calls". Each investigation still starts only when you press
   Start investigation, and its report shows an estimated model cost.


Your data
---------
Reports, settings (including your API keys, stored as plain text) and uploads stay
on this computer:
Windows: %APPDATA%\Clear Context
macOS:   ~/Library/Application Support/Clear Context
Linux:   ~/.local/share/Clear Context
The text, links and files of an investigation are sent to Meta and to the search
services you enable.


Remove it
---------
Delete the "Clear Context" folder. To also remove your reports and settings, delete
the data folder above.


Chrome extension
----------------
The extension is a separate download on the release page
(Clear-Context-chrome-extension.zip). Unzip it, open chrome://extensions, turn on
Developer mode, choose "Load unpacked" and select the unzipped folder. It finds this
app by itself while the app is running.


License: MIT (see LICENSE). Third-party components keep their own licenses; video
decoding bundles FFmpeg libraries under the LGPL through PyAV.
