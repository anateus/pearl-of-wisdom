(() => {
  const controls = document.getElementById("scenario-controls");
  const announcement = document.getElementById("scenario-announcement");
  const choose = (identifier, announce) => {
    document.querySelectorAll("[data-scenario]").forEach((element) => {
      element.classList.toggle("is-active", element.dataset.scenario === identifier);
    });
    for (const doc of window.Bokeh?.documents ?? []) {
      const source = doc.get_model_by_name("pearl-interval-data");
      if (source) {
        source.data = {
          ...source.data,
          color: source.data.identifier.map((id) => id === identifier ? "#2257a6" : "#53606c"),
        };
        for (const id of source.data.identifier) {
          const curve = doc.get_model_by_name(`pearl-ecdf-${id}`);
          if (curve) curve.line_color = id === identifier ? "#2257a6" : "#53606c";
        }
      }
    }
    if (announce) {
      const active = document.querySelector(".scenario-answer.is-active");
      announcement.textContent = active.querySelector("h2").textContent + ". " + active.querySelector(".answer").textContent;
    }
    window.dispatchEvent(new Event("resize"));
  };
  document.body.classList.add("enhanced");
  if (controls.querySelectorAll("input").length > 1) controls.hidden = false;
  controls.addEventListener("change", (event) => {
    if (event.target instanceof HTMLInputElement) choose(event.target.value, true);
  });
  document.querySelectorAll("details").forEach((element) => {
    element.addEventListener("toggle", () => window.dispatchEvent(new Event("resize")));
  });
})();
