const $ = (id) => document.getElementById(id);
const KUNCI = ["folder_sumber", "folder_output", "pdf_peta", "kode_flight"];

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
    tr.innerHTML = `<td>${b.kode}</td><td>${b.divisi || "-"}</td><td>${b.luas_ha ?? ""}</td>`;
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
    tr.innerHTML = `<td>${it.divisi} ${it.kode}</td><td>${it.layer}</td><td>${it.status}</td>` +
                   `<td>${(it.size / 1e6).toFixed(1)} MB</td><td>${it.error}</td>`;
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
