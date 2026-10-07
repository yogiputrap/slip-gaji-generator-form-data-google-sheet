import os
import argparse
import generator

DEFAULT_SHEET = os.environ.get("SHEET_URL", "")

def main():
    parser = argparse.ArgumentParser(description="Auto Generate Slip Gaji dari Google Sheet / Excel")
    parser.add_argument("--sheet", default=DEFAULT_SHEET, help="URL Google Sheet atau path file Excel .xlsx")
    parser.add_argument("--output-dir", default="./output", help="Direktori penyimpanan file PDF hasil generate")
    parser.add_argument("--logo", default="assets/logo_default.png", help="Path file logo perusahaan")
    parser.add_argument("--signature", default="", help="Path file gambar tanda tangan (opsional)")
    parser.add_argument("--period", default="September 2026", help="Periode Gaji (misal: September 2026)")
    parser.add_argument("--slip-date", default="Bandung, 29 September 2026", help="Tanggal Slip")
    parser.add_argument("--signer-title", default="Bagian Keuangan,", help="Jabatan Penanda Tangan")
    parser.add_argument("--signer-name", default="Reza Fauzi", help="Nama Penanda Tangan")
    parser.add_argument("--id", type=int, default=None, help="Generate hanya untuk nomor urut ID tertentu")
    parser.add_argument("--zip", action="store_true", help="Kemas semua PDF ke dalam file ZIP")

    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Mengambil data penggajian dari: {args.sheet}")
    try:
        res = generator.fetch_data_from_sheet(args.sheet)
        if isinstance(res, tuple) and len(res) == 3:
            employees, detected_period, detected_slip_date = res
            if detected_period and args.period == "August 2026":
                args.period = detected_period
            if detected_slip_date and args.slip_date == "Bandung, 29 Agustus 2026":
                args.slip_date = detected_slip_date
        else:
            employees = res
        print(f"Berhasil mengekstrak {len(employees)} data karyawan.")
    except Exception as e:
        print(f"Error saat mengambil data: {e}")
        return

    if args.id is not None:
        employees = [e for e in employees if e["id"] == args.id]
        if not employees:
            print(f"Karyawan dengan ID {args.id} tidak ditemukan.")
            return

    config = {
        "logo_path": args.logo if os.path.exists(args.logo) else "",
        "signature_path": args.signature if os.path.exists(args.signature) else "",
        "period": args.period,
        "slip_date": args.slip_date,
        "signer_title": args.signer_title,
        "signer_name": args.signer_name
    }

    if args.zip:
        period_slug = args.period.replace(" ", "_")
        zip_path = os.path.join(args.output_dir, f"Kumpulan_Slip_Gaji_{period_slug}.zip")
        print(f"Membuat file ZIP untuk {len(employees)} karyawan...")
        generator.batch_generate_zip(employees, config, zip_path)
        print(f"Selesai! File ZIP tersimpan di: {zip_path}")
    else:
        print(f"Memulai pembuatan PDF untuk {len(employees)} karyawan...")
        period_slug = args.period.replace(" ", "_")
        for emp in employees:
            safe_nama = "".join(c for c in emp['nama'] if c.isalnum() or c in (' ', '_', '-')).strip()
            pdf_path = os.path.join(args.output_dir, f"Slip_Gaji_{period_slug}_{safe_nama}.pdf")
            html = generator.render_slip_html(emp, config)
            ok = generator.generate_pdf_from_html(html, pdf_path)
            if ok:
                print(f"✓ Berhasil: {pdf_path}")
            else:
                print(f"✗ Gagal: {pdf_path}")
        print("Selesai generate semua slip gaji!")

if __name__ == "__main__":
    main()
