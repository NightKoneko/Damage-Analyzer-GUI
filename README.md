# HSR Damage Analyzer GUI

Made to be used with https://github.com/hessiser/veritas

This is still a work in progress

## How to use:

1. `git clone https://github.com/NightKoneko/Damage-Analyzer-GUI.git`

2. `pip install -r requirements.txt`

2. Inject https://github.com/hessiser/veritas (You can download a prebuilt veritas dll from releases or alternatively build it yourself) into the game. This can be done with a tool like https://github.com/lanylow/genshin-utility or Cheat Engine

   * In the case of https://github.com/lanylow/genshin-utility, rename `veritas.dll` to `library.dll` and replace the previous `library.dll` with it. **Make sure to run `loader.exe` as administrator.**

3. Run `damageanalyzer_gui.py`

4. Click the 'Connect' button

5. Enter battle in-game

6. Damage should now be logging and visualizations (graphs) updating accordingly
