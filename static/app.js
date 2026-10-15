const $ = (id) => document.getElementById(id);
const KUNCI = ["folder_sumber", "folder_output", "pdf_peta", "kode_flight", "shp_kebun"];

async function muatConfig() {
  const c = await (await fetch("/api/config")).json();
  for (const k of KUNCI) $(k).value = c[k] ?? "";
}

async function simpanConfig() {
  const body = {};
  for (const k of KUNCI) body[k] = $(k).value.trim();
  const r = await (await fetch("/api/config", {method: "POST",
    headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)})).json();
  $("status-simpan").textContent = r.ok ? "Tersimpan." : "Gagal menyimpan.";
}

async function pindai() {
  $("hasil-pindai").textContent = "Memindai…";
  const r = await (await fetch("/api/pindai", {method: "POST"})).json();
  if (!r.ok) { $("hasil-pindai").textContent = "GAGAL: " + r.error; return; }
  const nLayer = Object.keys(r.layers).length;
  $("hasil-pindai").textContent =
    `${r.n_blok} blok × ${nLayer} layer = ${r.n_baris} file; ` +
    `estimasi ${(r.estimasi_byte / 1e9).toFixed(1)} GB; ` +
    `disk bebas ${(r.disk_bebas_byte / 1e9).toFixed(1)} GB` +
    (r.cukup_disk ? "" : " — PERINGATAN: disk mungkin tidak cukup");
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
    const btn = document.createElement("button");
    btn.textContent = "Simpan";
    btn.onclick = async () => {
      await fetch("/api/blok/divisi", {method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({kode: b.kode, divisi: inp.value.trim()})});
      btn.textContent = "Tersimpan";
    };
    td.append(inp, btn);
    tr.append(td);
    tb.append(tr);
  }
}

async function jalankan() {
  const r = await (await fetch("/api/jalankan", {method: "POST"})).json();
  if (!r.ok) { alert("Gagal: " + r.error); return; }
  setTimeout(polling, 500);
}

function warna(status) {
  return {selesai: "#c8f7c5", gagal: "#f7c5c5", berjalan: "#fff3b0",
          dilewati: "#e0e0e0", pending: "#ffffff"}[status] || "#fff";
}

async function polling() {
  const s = await (await fetch("/api/status")).json();
  $("progress-teks").textContent = `${s.selesai}/${s.total} (gagal ${s.gagal})`;
  $("progress-isi").style.width = s.total ? `${Math.round(s.selesai / s.total * 100)}%` : "0%";
  const tb = $("tabel-status").querySelector("tbody");
  tb.innerHTML = "";
  for (const it of s.items) {
    const tr = document.createElement("tr");
    tr.style.background = warna(it.status);
    for (const v of [`${it.divisi} ${it.kode}`, it.layer, it.status,
                     `${(it.size / 1e6).toFixed(1)} MB`, it.error]) {
      const cell = document.createElement("td");
      cell.textContent = v ?? "";
      tr.append(cell);
    }
    const td = document.createElement("td");
    if (it.status === "gagal") {
      const b = document.createElement("button");
      b.textContent = "Coba ulang";
      b.onclick = () => {
        fetch("/api/ulangi", {method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({kode: it.kode})});
        setTimeout(polling, 500);
      };
      td.append(b);
    }
    tr.append(td);
    tb.append(tr);
  }
  $("log").textContent = s.log_tail || "";
  if (s.aktif) setTimeout(polling, 1000);
}

$("btn-simpan").onclick = simpanConfig;
$("btn-pindai").onclick = pindai;
$("btn-jalankan").onclick = jalankan;
$("btn-batalkan").onclick = () => fetch("/api/batalkan", {method: "POST"});
$("btn-buka").onclick = () => fetch("/api/buka-folder", {method: "POST"});
muatConfig().then(polling);
muatKartu();

// --- Tab Validasi: galeri + viewer ---
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
    return;
  }
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
}, {passive: false});

$("vw-img").addEventListener("pointerdown", (e) => {
  vwDrag = {x: e.clientX - vwX, y: e.clientY - vwY};
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
  $("btn-kartu-buat").disabled = true;
  const r = await (await fetch("/api/kartu/buat", {method: "POST"})).json();
  if (!r.ok) {
    $("status-kartu").textContent = "GAGAL: " + r.error;
    $("btn-kartu-buat").disabled = false;
    return;
  }
  pollingKartu();
}

async function pollingKartu() {
  const s = await (await fetch("/api/kartu/status")).json();
  if (s.aktif) {
    $("status-kartu").textContent = `Membuat kartu… ${s.i}/${s.n} ${s.pesan}`;
    setTimeout(pollingKartu, 700);
    return;
  }
  $("btn-kartu-buat").disabled = false;
  if (s.error) {
    $("status-kartu").textContent = "GAGAL: " + s.error;
  } else {
    const dilewati = (s.dilewati || []).length;
    $("status-kartu").textContent =
      `Selesai: ${s.selesai ?? 0} kartu` + (dilewati ? `, ${dilewati} blok dilewati (belum ada hasil ekspor)` : "") +
      ` → ${s.dest || ""}`;
    muatKartu();
  }
}

$("btn-kartu-buat").onclick = buatKartu;
