const $ = (id) => document.getElementById(id);
const KUNCI = ["folder_sumber", "folder_output", "pdf_peta", "kode_flight", "shp_kebun"];
const JUDUL_TAHAP = { setup: "1 · Setup", pindai: "2 · Pindai", jalankan: "3 · Jalankan", validasi: "4 · Validasi" };
const JENIS_PIL = { selesai: "ok", gagal: "err", berjalan: "warn", dilewati: "idle", pending: "idle" };

// --- Tema terang/gelap ---
const KUNCI_TEMA = "ekspor-tema";

function temaAwal() {
  const t = localStorage.getItem(KUNCI_TEMA);
  if (t === "terang" || t === "gelap") return t;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "gelap" : "terang";
}

function terapkanTema(t) {
  document.documentElement.dataset.tema = t;
  $("ikon-gelap").classList.toggle("sembunyi", t === "gelap");
  $("ikon-terang").classList.toggle("sembunyi", t !== "gelap");
  $("teks-tema").textContent = t === "gelap" ? "Mode terang" : "Mode gelap";
}

let tema = temaAwal();
terapkanTema(tema);
$("btn-tema").onclick = () => {
  tema = tema === "gelap" ? "terang" : "gelap";
  localStorage.setItem(KUNCI_TEMA, tema);
  terapkanTema(tema);
};

// --- Navigasi 4 tahap ---
let tahapAktif = "setup";

function pindahTahap(nama) {
  tahapAktif = nama;
  document.querySelectorAll(".nav-item").forEach((b) => {
    const on = b.dataset.tahap === nama;
    b.classList.toggle("aktif", on);
    b.classList.remove("disarankan");
    if (on) b.setAttribute("aria-current", "step");
    else b.removeAttribute("aria-current");
  });
  document.querySelectorAll(".panel").forEach((p) => {
    p.classList.toggle("sembunyi", p.id !== "tahap-" + nama);
  });
  $("judul-tahap").textContent = JUDUL_TAHAP[nama];
}

document.querySelectorAll(".nav-item").forEach((b) => {
  b.onclick = () => pindahTahap(b.dataset.tahap);
});

function sarankan(nama) {
  if (tahapAktif === nama) return;
  document.querySelector(`.nav-item[data-tahap="${nama}"]`).classList.add("disarankan");
}

// --- Badge status tahap ---
function setBadge(id, teks, jenis) {
  const b = $(id);
  b.textContent = teks;
  b.className = "nav-badge b-" + (jenis || "idle");
}

function chip(teks, jenis) {
  const s = document.createElement("span");
  s.className = "chip" + (jenis ? " " + jenis : "");
  s.textContent = teks;
  return s;
}

function gb(bita) {
  return (bita / 1e9).toLocaleString("id-ID", { maximumFractionDigits: 1 }) + " GB";
}

// --- Konfigurasi ---
function segarkanSetup() {
  const terisi = KUNCI.filter((k) => $(k).value.trim()).length;
  setBadge("badge-setup", terisi === KUNCI.length ? "lengkap" : `${terisi}/${KUNCI.length} terisi`,
           terisi === KUNCI.length ? "ok" : "idle");
  const out = $("folder_output").value.trim();
  $("jalur-output").textContent = out ? out.split(/[\\/]/).filter(Boolean).pop() : "—";
  $("jalur-output").title = out;
  const fl = $("kode_flight").value.trim();
  $("jalur-flight").textContent = fl ? "Flight " + fl : "Flight —";
}

async function muatConfig() {
  const c = await (await fetch("/api/config")).json();
  for (const k of KUNCI) $(k).value = c[k] ?? "";
  segarkanSetup();
}

async function simpanConfig() {
  const body = {};
  for (const k of KUNCI) body[k] = $(k).value.trim();
  const r = await (await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })).json();
  const s = $("status-simpan");
  s.textContent = r.ok ? "Tersimpan." : "Gagal menyimpan.";
  s.className = "status-aksi " + (r.ok ? "teks-ok" : "teks-err");
  segarkanSetup();
}

async function telusuri(btn) {
  const inp = $(btn.dataset.sasaran);
  const g = $("galat-pilih");
  const semua = document.querySelectorAll(".btn-telusuri");
  const teksAsli = btn.textContent;
  g.classList.add("sembunyi");
  semua.forEach((b) => { b.disabled = true; });
  btn.textContent = "Memilih…";
  try {
    const r = await (await fetch("/api/pilih", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jenis: btn.dataset.jenis, nilai: inp.value.trim() })
    })).json();
    if (!r.ok) {
      g.textContent = "Gagal membuka dialog: " + r.error;
      g.classList.remove("sembunyi");
    } else if (r.path) {
      inp.value = r.path;
      segarkanSetup();
    }
  } catch (e) {
    g.textContent = "Gagal menghubungi server: " + e;
    g.classList.remove("sembunyi");
  } finally {
    btn.textContent = teksAsli;
    semua.forEach((b) => { b.disabled = false; });
  }
}

// --- Tahap 2: pindai ---
async function pindai() {
  const btn = $("btn-pindai");
  const kotak = $("hasil-pindai");
  btn.disabled = true;
  kotak.textContent = "";
  kotak.append(chip("Memindai…", "memuat"));
  const r = await (await fetch("/api/pindai", { method: "POST" })).json();
  btn.disabled = false;
  kotak.textContent = "";
  if (!r.ok) {
    kotak.append(chip("GAGAL: " + r.error, "err"));
    setBadge("badge-pindai", "gagal", "err");
    return;
  }
  const nLayer = Object.keys(r.layers).length;
  kotak.append(
    chip(`${r.n_blok} blok × ${nLayer} layer`),
    chip(`${r.n_baris} file`),
    chip("estimasi " + gb(r.estimasi_byte)),
    chip("disk bebas " + gb(r.disk_bebas_byte), r.cukup_disk ? "" : "warn")
  );
  if (!r.cukup_disk) kotak.append(chip("disk mungkin tidak cukup", "err"));
  setBadge("badge-pindai", `${r.n_blok} blok`, "ok");
  $("ringkas-status").textContent = `Pindai: ${r.n_blok} blok · ${r.n_baris} file`;
  sarankan("jalankan");
  const tb = $("tabel-blok").querySelector("tbody");
  tb.innerHTML = "";
  for (const b of r.blok) {
    const tr = document.createElement("tr");
    for (const v of [b.kode, b.divisi || "-", b.luas_ha ?? ""]) {
      const cell = document.createElement("td");
      cell.textContent = v;
      tr.append(cell);
    }
    const td = document.createElement("td");
    const inp = document.createElement("input");
    inp.value = b.divisi || "";
    const btnSimpan = document.createElement("button");
    btnSimpan.className = "btn btn-sekunder btn-kecil";
    btnSimpan.textContent = "Simpan";
    btnSimpan.onclick = async () => {
      await fetch("/api/blok/divisi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kode: b.kode, divisi: inp.value.trim() })
      });
      btnSimpan.textContent = "Tersimpan";
    };
    td.append(inp, " ", btnSimpan);
    tr.append(td);
    tb.append(tr);
  }
}

// --- Tahap 3: jalankan + polling ---
async function jalankan() {
  const btn = $("btn-jalankan");
  const g = $("galat-jalankan");
  btn.disabled = true;
  g.classList.add("sembunyi");
  const r = await (await fetch("/api/jalankan", { method: "POST" })).json();
  btn.disabled = false;
  if (!r.ok) {
    g.textContent = "Gagal menjalankan: " + r.error;
    g.classList.remove("sembunyi");
    return;
  }
  setBadge("badge-jalankan", "menyiapkan…", "warn");
  setTimeout(polling, 500);
}

let sempatAktif = false;

async function polling() {
  const s = await (await fetch("/api/status")).json();
  $("progress-teks").textContent = `${s.selesai}/${s.total} (gagal ${s.gagal})`;
  $("progress-isi").style.width = s.total ? `${Math.round((s.selesai / s.total) * 100)}%` : "0%";
  const ringkas = $("ringkas-status");
  if (s.aktif) {
    setBadge("badge-jalankan", `${s.selesai}/${s.total} jalan`, "warn");
    ringkas.textContent = `Ekspor berjalan — ${s.selesai}/${s.total}${s.gagal ? ` · ${s.gagal} gagal` : ""}`;
    ringkas.className = "ringkas hidup";
  } else if (s.total > 0) {
    setBadge("badge-jalankan", s.gagal ? `${s.gagal} gagal` : `${s.selesai}/${s.total} selesai`,
             s.gagal ? "err" : "ok");
    ringkas.textContent = `Batch ${s.selesai}/${s.total}${s.gagal ? ` · ${s.gagal} gagal` : ""}`;
    ringkas.className = "ringkas";
    if (sempatAktif) sarankan("validasi");
  }
  sempatAktif = s.aktif;
  const tb = $("tabel-status").querySelector("tbody");
  tb.innerHTML = "";
  for (const it of s.items) {
    const tr = document.createElement("tr");
    tr.className = "baris-" + (it.status || "pending");
    const pil = document.createElement("span");
    pil.className = "pil pil-" + (JENIS_PIL[it.status] || "idle");
    pil.textContent = it.status || "";
    for (const v of [`${it.divisi} ${it.kode}`, it.layer]) {
      const cell = document.createElement("td");
      cell.textContent = v ?? "";
      tr.append(cell);
    }
    const tdPil = document.createElement("td");
    tdPil.append(pil);
    tr.append(tdPil);
    for (const v of [`${(it.size / 1e6).toLocaleString("id-ID", { maximumFractionDigits: 1 })} MB`, it.error]) {
      const cell = document.createElement("td");
      cell.textContent = v ?? "";
      tr.append(cell);
    }
    const tdAksi = document.createElement("td");
    if (it.status === "gagal") {
      const b = document.createElement("button");
      b.className = "btn btn-sekunder btn-kecil";
      b.textContent = "Coba ulang";
      b.onclick = () => {
        fetch("/api/ulangi", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ kode: it.kode })
        });
        setTimeout(polling, 500);
      };
      tdAksi.append(b);
    }
    tr.append(tdAksi);
    tb.append(tr);
  }
  $("log").textContent = s.log_tail || "";
  if (s.aktif) setTimeout(polling, 1000);
}

// --- Tahap 4: kartu validasi + viewer ---
let kartuDaftar = [], kartuIdx = 0, vwZoom = 1, vwX = 0, vwY = 0, vwDrag = null;

function urlKartu(file) {
  return "/api/kartu/file/" + encodeURIComponent(file);
}

async function muatKartu() {
  const r = await (await fetch("/api/kartu")).json();
  kartuDaftar = r.kartu || [];
  const g = $("galeri-kartu");
  g.innerHTML = "";
  if (!kartuDaftar.length) {
    g.textContent = "Belum ada kartu validasi — klik \"Buat/Perbarui Kartu Validasi\" setelah ekspor selesai.";
    setBadge("badge-validasi", "belum", "idle");
    return;
  }
  setBadge("badge-validasi", `${kartuDaftar.length} kartu`, "ok");
  kartuDaftar.forEach((k, i) => {
    const div = document.createElement("div");
    div.className = "thumb";
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = urlKartu(k.file);
    img.alt = "Kartu " + k.kode;
    img.onclick = () => bukaViewer(i);
    const cap = document.createElement("div");
    cap.textContent = k.kode + (k.iou != null ? ` — IoU ${k.iou.toFixed(1)}%` : "");
    div.append(img, cap);
    g.append(div);
  });
}

function terapkanViewer() {
  $("vw-img").style.transform = `translate(${vwX}px, ${vwY}px) scale(${vwZoom})`;
}

function aturGambar() {
  const k = kartuDaftar[kartuIdx];
  if (!k) return;
  vwZoom = 1; vwX = 0; vwY = 0;
  const img = $("vw-img");
  img.src = urlKartu(k.file);
  terapkanViewer();
  $("vw-label").textContent =
    `${kartuIdx + 1}/${kartuDaftar.length} — blok ${k.kode}` +
    (k.iou != null ? ` (IoU ${k.iou.toFixed(1)}%, geser ${k.geser_m.toFixed(1)} m)` : "");
}

function bukaViewer(i) {
  kartuIdx = i;
  $("viewer").classList.remove("sembunyi");
  aturGambar();
}

function tutupViewer() { $("viewer").classList.add("sembunyi"); }

function gantiKartu(arah) {
  kartuIdx = (kartuIdx + arah + kartuDaftar.length) % kartuDaftar.length;
  aturGambar();
}

$("vw-tutup").onclick = tutupViewer;
$("vw-kiri").onclick = () => gantiKartu(-1);
$("vw-kanan").onclick = () => gantiKartu(1);

document.addEventListener("keydown", (e) => {
  if ($("viewer").classList.contains("sembunyi")) return;
  if (e.key === "Escape") tutupViewer();
  else if (e.key === "ArrowLeft") gantiKartu(-1);
  else if (e.key === "ArrowRight") gantiKartu(1);
});

$("vw-panggung").addEventListener("wheel", (e) => {
  e.preventDefault();
  const f = e.deltaY < 0 ? 1.15 : 1 / 1.15;
  vwZoom = Math.min(10, Math.max(0.4, vwZoom * f));
  terapkanViewer();
}, { passive: false });

$("vw-img").addEventListener("pointerdown", (e) => {
  vwDrag = { x: e.clientX - vwX, y: e.clientY - vwY };
  $("vw-img").setPointerCapture(e.pointerId);
});
$("vw-img").addEventListener("pointermove", (e) => {
  if (!vwDrag) return;
  vwX = e.clientX - vwDrag.x;
  vwY = e.clientY - vwDrag.y;
  terapkanViewer();
});
$("vw-img").addEventListener("pointerup", () => { vwDrag = null; });
$("vw-img").ondblclick = () => { vwZoom = 1; vwX = 0; vwY = 0; terapkanViewer(); };

async function buatKartu() {
  $("status-kartu").textContent = "Memulai…";
  $("status-kartu").className = "status-aksi";
  $("btn-kartu-buat").disabled = true;
  setBadge("badge-validasi", "membuat…", "warn");
  const r = await (await fetch("/api/kartu/buat", { method: "POST" })).json();
  if (!r.ok) {
    $("status-kartu").textContent = "GAGAL: " + r.error;
    $("status-kartu").className = "status-aksi teks-err";
    $("btn-kartu-buat").disabled = false;
    setBadge("badge-validasi", "gagal", "err");
    return;
  }
  pollingKartu();
}

async function pollingKartu() {
  const s = await (await fetch("/api/kartu/status")).json();
  if (s.aktif) {
    $("status-kartu").textContent = `Membuat kartu… ${s.i}/${s.n} ${s.pesan}`;
    setBadge("badge-validasi", `${s.i}/${s.n}`, "warn");
    setTimeout(pollingKartu, 700);
    return;
  }
  $("btn-kartu-buat").disabled = false;
  if (s.error) {
    $("status-kartu").textContent = "GAGAL: " + s.error;
    $("status-kartu").className = "status-aksi teks-err";
    setBadge("badge-validasi", "gagal", "err");
  } else {
    const dilewati = (s.dilewati || []).length;
    $("status-kartu").textContent =
      `Selesai: ${s.selesai ?? 0} kartu` + (dilewati ? `, ${dilewati} blok dilewati (belum ada hasil ekspor)` : "") +
      ` → ${s.dest || ""}`;
    $("status-kartu").className = "status-aksi teks-ok";
    muatKartu();
  }
}

// --- Binding & inisialisasi ---
$("btn-simpan").onclick = simpanConfig;
document.querySelectorAll(".btn-telusuri").forEach((b) => {
  b.onclick = () => telusuri(b);
});
$("btn-pindai").onclick = pindai;
$("btn-jalankan").onclick = jalankan;
$("btn-batalkan").onclick = () => fetch("/api/batalkan", { method: "POST" });
$("btn-buka").onclick = () => fetch("/api/buka-folder", { method: "POST" });
$("btn-kartu-buat").onclick = buatKartu;

muatConfig().then(polling);
muatKartu();
