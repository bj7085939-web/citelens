const $ = (s) => document.querySelector(s);

fetch("/api/health").then(r => r.json()).then(h => {
  const m = $("#mode");
  m.textContent = h.live
    ? `LIVE · ${h.model} on Nebius Token Factory`
    : "DEMO MODE · offline sample corpus (add API keys for live)";
  if (h.live) m.classList.add("live");
}).catch(() => { $("#mode").textContent = "server unreachable"; });

$("#ask-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("#q").value.trim();
  if (!q) return;
  const btn = $("#go"), st = $("#status");
  btn.disabled = true;
  st.textContent = "Searching sources and drafting a cited answer…";
  $("#answer-wrap").hidden = true;
  try {
    const r = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "request failed");
    render(data);
    st.textContent = data.mode === "live"
      ? "Live answer — retrieval by Tavily, generation by Nemotron."
      : "Demo answer from the bundled sample corpus (deterministic, no API keys).";
  } catch (err) {
    st.textContent = "Error: " + err.message;
  } finally {
    btn.disabled = false;
  }
});

function render(data) {
  const ans = $("#answer");
  ans.innerHTML = "";
  data.segments.forEach(seg => {
    const span = document.createElement("span");
    span.className = "seg" + (seg.cited ? "" : " uncited");
    span.textContent = seg.text + " ";
    seg.refs.forEach(n => {
      const sup = document.createElement("sup");
      sup.className = "ref";
      const a = document.createElement("a");
      a.href = "#src-" + n; a.textContent = "[" + n + "]";
      sup.appendChild(a);
      span.appendChild(sup); span.appendChild(document.createTextNode(" "));
    });
    ans.appendChild(span);
  });

  const c = $("#coverage");
  const pct = Math.round(data.stats.coverage * 100);
  c.textContent = `Citation coverage: ${data.stats.cited}/${data.stats.sentences} sentences (${pct}%)`;
  c.className = "coverage " + (data.stats.coverage === 1 ? "ok" : "bad");

  const box = $("#sources");
  box.innerHTML = "";
  data.sources.forEach(s => {
    const d = document.createElement("div");
    d.className = "src"; d.id = "src-" + s.id;
    const snippet = s.content.length > 320 ? s.content.slice(0, 320) + "…" : s.content;
    d.innerHTML = `<div class="t">[${s.id}] </div><div class="u"></div>
                   <div class="d"></div><p></p>`;
    d.querySelector(".t").append(document.createTextNode(s.title));
    const a = document.createElement("a");
    a.href = s.url; a.target = "_blank"; a.rel = "noopener"; a.textContent = s.url;
    d.querySelector(".u").appendChild(a);
    d.querySelector(".d").textContent =
      [s.published_date, s.score != null ? "relevance " + s.score.toFixed(2) : ""]
        .filter(Boolean).join(" · ");
    d.querySelector("p").textContent = snippet;
    box.appendChild(d);
  });
  $("#answer-wrap").hidden = false;
}
