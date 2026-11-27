# Bloomfit — Working Prototype

## What's included
- Redesigned pink-and-blush Bloomfit interface with the original sequential flow.
- Flask backend and SQLite database.
- Demo account creation/sign-in (first login creates the account; later logins check password).
- Profile persistence, wardrobe image upload, and real virtual try-on integration attempt.
- Virtual try-on uses the community Hugging Face Space `Nymbo/Virtual-Try-On` (IDM-VTON) through `gradio_client`.

## Run on Windows
1. Install Python 3.10 or newer.
2. Extract this ZIP.
3. Open PowerShell in the `Bloomfit_AI` folder.
4. Run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

5. Open `http://127.0.0.1:5000`.

If PowerShell blocks activation, run:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

## Virtual try-on notes
- Upload a clear, well-lit, front-facing person photo and a clean garment product image.
- The backend calls the Nymbo IDM-VTON Gradio Space. It is a free community demo, not a guaranteed production service. It may queue, sleep, or hit daily GPU limits.
- This project does not fake the result: if the model call fails, the website displays an error rather than showing the two source images as a generated result.
- IDM-VTON's model/demo license is CC BY-NC-SA 4.0. It is suitable for a non-commercial student prototype subject to its license; do not use commercially without checking licensing.
- Photos are sent to the external Hugging Face Space for inference. Use only photos you have permission to upload.

## Important prototype limitations
- Authentication is a local demo account flow, not production-grade auth.
- Profile and wardrobe data are stored locally in SQLite.
- The outfit recommendation screen currently produces rule-based styling suggestions, not a trained ML model.
- The free model currently focuses on upper-body clothing in its mask-generation path. Full dresses/maxi dresses may be less reliable; test with an upper-body garment first.
- For a public deployment, change `FLASK_SECRET_KEY`, add CSRF protection, user privacy/deletion controls, rate limiting, and secure hosting.
