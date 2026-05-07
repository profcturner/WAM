/* static/widgets/hours_percentage_widget.js */

(function () {
  "use strict";

  function initWidget(container) {
    const name = container.dataset.name;
    const toggleInputs = container.querySelectorAll(`input[name="${name}_0"]`);
    const hoursInput   = container.querySelector(`input[name="${name}_1"]`);
    const pctInput     = container.querySelector(`input[name="${name}_2"]`);

    if (!toggleInputs.length || !hoursInput || !pctInput) return;

    function update() {
      const selected = container.querySelector(`input[name="${name}_0"]:checked`);
      const isHours = selected && selected.value === "H";

      hoursInput.classList.toggle("hp-hidden", !isHours);
      pctInput.classList.toggle("hp-hidden", isHours);

      // Clear the hidden field's value so it doesn't interfere with validation
      if (isHours) {
        pctInput.value = "";
      } else {
        hoursInput.value = "";
      }
    }

    toggleInputs.forEach(function (radio) {
      radio.addEventListener("change", update);
    });

    // Run once on load to reflect the current/initial state
    update();
  }

  function init() {
    document.querySelectorAll(".hours-percentage-widget").forEach(initWidget);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
