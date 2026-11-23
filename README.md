# Modul KRS (Kartu Rencana Studi) — Sistem Manajemen Akademik (Minggu 5–6)

Modul layanan API untuk pengelolaan proses Kartu Rencana Studi (KRS) mahasiswa, lengkap dengan validasi aturan dan mesin status (*state machine*) alur KRS.

## Struktur Proyek
- `app/main.py` — *entrypoint* aplikasi / endpoint API modul KRS
- `app/state_machine.py` — logika transisi status alur KRS
- `app/validators.py` — validasi data dan aturan pengambilan/perubahan KRS

## Cara Menjalankan Secara Lokal

1. Pastikan posisi direktori berada di folder proyek:
   ```powershell
   cd "C:\Users\HYPE AMD\OneDrive\Documents\coding coding\modul-krs-5-6"