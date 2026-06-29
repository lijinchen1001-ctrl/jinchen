# Hatch Desktop Pet

Windows desktop pet made from the referenced multi-view creature images.

## Files

- `desktop_pet.py` - native Windows transparent desktop pet app.
- `run_desktop_pet.bat` - double-click launcher.
- `hatch_pet_*.png` - idle, sleep, wave, and hatch sprites.
- `walk_side_*.png` - side-view walking animation frames.

## Run

Double-click:

```bat
run_desktop_pet.bat
```

Or run from PowerShell:

```powershell
cd D:\GeneratedPet\hatch_pet
python desktop_pet.py
```

If Pillow is missing:

```powershell
python -m pip install -r requirements.txt
```

## Behavior

- Sleeps at the bottom of the desktop by default.
- Click the pet to wake it, wave, and walk along the bottom of the screen for 30 seconds.
- After walking, it transitions back to idle and then sleep.
- Right-click menu: wake, sleep now, resize, or quit.

