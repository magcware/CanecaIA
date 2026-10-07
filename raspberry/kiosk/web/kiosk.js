const stage = document.getElementById("stage");
let currentKey = "";

document.body.addEventListener("pointerdown", () => {
  if (!document.fullscreenElement && document.documentElement.requestFullscreen) {
    document.documentElement.requestFullscreen().catch(() => {});
  }
});

function render(data) {
  document.body.dataset.state = data.state;
  document.body.dataset.color = data.color || "";
  const photo = data.photo ? `/media/photo?session=${data.session}` : "";
  const bin = data.bin ? `/media/bin?color=${encodeURIComponent(data.color)}` : "";

  if (data.state === "waiting" || data.state === "detected") {
    stage.innerHTML = `
      <section class="panel">
        <h1>${escapeHtml(data.title)}</h1>
      </section>`;
    return;
  }

  if (data.state === "processing") {
    stage.innerHTML = `
      <section class="panel split">
        <div class="photo-frame busy">
          <img alt="Residuo capturado" src="${photo}">
        </div>
        <div class="result-copy">
          <h1>${escapeHtml(data.title)}</h1>
          <div class="dots" aria-hidden="true"><i></i><i></i><i></i></div>
        </div>
      </section>`;
    return;
  }

  if (data.state === "result") {
    const color = escapeHtml(data.color || "");
    stage.innerHTML = `
      <section class="panel split">
        <div class="photo-frame">
          <img alt="Residuo capturado" src="${photo}">
        </div>
        <div class="result-copy">
          <p class="eyebrow">Tu residuo</p>
          <p class="label ${color}">${escapeHtml(data.label || data.title)}</p>
          ${bin ? `<div class="bin-wrap"><img alt="Caneca ${color}" src="${bin}"></div>` : ""}
        </div>
      </section>`;
    return;
  }

  if (data.state === "thanks") {
    stage.innerHTML = `
      <section class="panel thanks">
        <h1>${escapeHtml(data.title)}</h1>
      </section>`;
    return;
  }

  stage.innerHTML = `
    <section class="panel error">
      <h1>${escapeHtml(data.title)}</h1>
    </section>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function tick() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    const data = await response.json();
    const key = `${data.session}:${data.state}:${data.color || ""}`;
    if (key !== currentKey) {
      currentKey = key;
      render(data);
    }
  } catch (error) {
    console.error(error);
  }
}

tick();
setInterval(tick, 300);
