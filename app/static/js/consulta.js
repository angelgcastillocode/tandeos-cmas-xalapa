(() => {
  "use strict";

  // Elementos de la página de inicio (index.html)
  const formInicio = document.getElementById("formConsulta");
  const inputInicio = document.getElementById("inputBusqueda");
  const btnSubmitInicio = document.getElementById("btnBuscar");
  const btnTextInicio = document.getElementById("btnBuscarTexto");
  const spinnerInicio = document.getElementById("btnBuscarSpinner");

  // Elementos de la página de calendario (/consulta)
  const formCalendario = document.getElementById("formBuscarCalendario");
  const inputCalendario = document.getElementById("inputBuscarCalendario");
  const dropdownCalendario = document.getElementById("autocompleteDropdown");

  // Secciones dinámicas de index.html (si existen)
  const secCargando = document.getElementById("secCargando");
  const secVacio = document.getElementById("secVacio");
  const secResultado = document.getElementById("secResultado");
  const vacioTitulo = document.getElementById("vacioTitulo");
  const vacioMensaje = document.getElementById("vacioMensaje");
  const resColonia = document.getElementById("resColonia");
  const resCodigoPostal = document.getElementById("resCodigoPostal");
  const resSector = document.getElementById("resSector");
  const resRed = document.getElementById("resRed");
  const resDisponibilidad = document.getElementById("resDisponibilidad");
  const gridCalendario = document.getElementById("gridCalendario");
  const secCoincidencias = document.getElementById("secCoincidencias");
  const listaCoincidencias = document.getElementById("listaCoincidencias");

  const diasSemanaNombres = [
    "Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"
  ];
  const diaHoyNombre = diasSemanaNombres[new Date().getDay()];

  function normalizar(texto) {
    if (!texto) return "";
    return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  // =========================================================================
  // 1. VALIDACIÓN EN CLIENTE
  // =========================================================================
  function validarEntrada(valor, inputElement) {
    const q = (valor || "").trim();
    if (!q) {
      if (inputElement) {
        inputElement.classList.add("is-invalid");
        inputElement.focus();
      }
      return false;
    }

    // Si es numérico, verificar que sean 5 dígitos
    if (/^\d+$/.test(q)) {
      if (q.length !== 5) {
        if (inputElement) {
          inputElement.setCustomValidity("El código postal debe contener exactamente 5 dígitos.");
          inputElement.reportValidity();
          inputElement.focus();
        }
        return false;
      }
    } else if (q.length < 2) {
      if (inputElement) {
        inputElement.setCustomValidity("Por favor escribe al menos 2 caracteres.");
        inputElement.reportValidity();
        inputElement.focus();
      }
      return false;
    }

    if (inputElement) {
      inputElement.setCustomValidity("");
      inputElement.classList.remove("is-invalid");
    }
    return true;
  }

  // =========================================================================
  // 2. AUTOCOMPLETADO ASÍNCRONO (/api/v1/tandeos/buscar)
  // =========================================================================
  let debounceTimer = null;
  let activeSuggestionIndex = -1;

  function crearDropdownAutocompletado(inputEl) {
    if (!inputEl) return null;
    let dropdown = inputEl.parentElement.querySelector(".autocomplete-dropdown");
    if (!dropdown) {
      dropdown = document.createElement("div");
      dropdown.className = "autocomplete-dropdown d-none shadow";
      dropdown.setAttribute("role", "listbox");
      inputEl.parentElement.style.position = "relative";
      inputEl.parentElement.appendChild(dropdown);
    }
    return dropdown;
  }

  async function consultarSugerenciasApi(termino) {
    try {
      const resp = await fetch(`/api/v1/tandeos/buscar?q=${encodeURIComponent(termino)}`);
      if (!resp.ok) return [];
      const data = await resp.json();
      if (!data.success || !data.encontrado) return [];

      const sugerencias = [];
      if (data.colonia) {
        sugerencias.push({
          nombre: data.colonia.nombre || data.colonia.nombre_colonia,
          cp: data.colonia.codigo_postal,
          sector: data.sector ? (data.sector.nombre || data.sector.nombre_sector) : "Sector Asignado"
        });
      }

      if (Array.isArray(data.coincidencias)) {
        data.coincidencias.forEach(c => {
          const nom = c.nombre || c.nombre_colonia;
          if (sugerencias.every(s => s.nombre !== nom)) {
            sugerencias.push({
              nombre: nom,
              cp: c.codigo_postal,
              sector: c.nombre_sector || "Sector Asignado"
            });
          }
        });
      }
      return sugerencias.slice(0, 6);
    } catch (err) {
      console.warn("Autocompletado no disponible:", err);
      return [];
    }
  }

  function renderizarSugerencias(dropdown, lista, inputEl, alSeleccionar) {
    if (!dropdown) return;
    dropdown.innerHTML = "";
    activeSuggestionIndex = -1;

    if (!lista || lista.length === 0) {
      dropdown.classList.add("d-none");
      return;
    }

    lista.forEach((item, idx) => {
      const row = document.createElement("a");
      row.href = `/consulta?q=${encodeURIComponent(item.nombre)}`;
      row.className = "autocomplete-item";
      row.setAttribute("role", "option");
      row.setAttribute("data-index", idx);
      row.innerHTML = `
        <div>
          <i class="bi bi-geo-alt-fill text-primary me-2" aria-hidden="true"></i>
          <strong>${item.nombre}</strong>
        </div>
        <div class="item-meta">
          <span class="badge bg-light text-secondary border me-1">C.P. ${item.cp}</span>
          <span>${item.sector}</span>
        </div>
      `;

      row.addEventListener("click", (e) => {
        if (alSeleccionar) {
          e.preventDefault();
          alSeleccionar(item.nombre);
        }
      });

      dropdown.appendChild(row);
    });

    dropdown.classList.remove("d-none");
  }

  function conectarAutocompletado(inputEl, alSeleccionar) {
    if (!inputEl) return;
    const dropdown = crearDropdownAutocompletado(inputEl);

    inputEl.addEventListener("input", () => {
      const val = inputEl.value.trim();
      inputEl.setCustomValidity("");
      clearTimeout(debounceTimer);

      if (val.length < 2) {
        if (dropdown) dropdown.classList.add("d-none");
        return;
      }

      debounceTimer = setTimeout(async () => {
        const sugerencias = await consultarSugerenciasApi(val);
        renderizarSugerencias(dropdown, sugerencias, inputEl, alSeleccionar);
      }, 250);
    });

    // Manejo accesible de teclado (Flechas, Enter, Escape)
    inputEl.addEventListener("keydown", (e) => {
      if (!dropdown || dropdown.classList.contains("d-none")) return;
      const items = dropdown.querySelectorAll(".autocomplete-item");
      if (items.length === 0) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        activeSuggestionIndex = (activeSuggestionIndex + 1) % items.length;
        actualizarSeleccionVisual(items);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        activeSuggestionIndex = (activeSuggestionIndex - 1 + items.length) % items.length;
        actualizarSeleccionVisual(items);
      } else if (e.key === "Enter" && activeSuggestionIndex >= 0) {
        e.preventDefault();
        items[activeSuggestionIndex].click();
      } else if (e.key === "Escape") {
        dropdown.classList.add("d-none");
      }
    });

    document.addEventListener("click", (e) => {
      if (!inputEl.contains(e.target) && (!dropdown || !dropdown.contains(e.target))) {
        if (dropdown) dropdown.classList.add("d-none");
      }
    });
  }

  function actualizarSeleccionVisual(items) {
    items.forEach((it, idx) => {
      it.classList.toggle("active", idx === activeSuggestionIndex);
      if (idx === activeSuggestionIndex) {
        it.scrollIntoView({ block: "nearest" });
      }
    });
  }

  // =========================================================================
  // 3. PÁGINA INICIO: BÚSQUEDA DINÁMICA
  // =========================================================================
  if (formInicio && inputInicio) {
    conectarAutocompletado(inputInicio, (nombreColonia) => {
      inputInicio.value = nombreColonia;
      ejecutarConsultaInicio(nombreColonia);
    });

    formInicio.addEventListener("submit", (e) => {
      e.preventDefault();
      if (!validarEntrada(inputInicio.value, inputInicio)) {
        return;
      }
      ejecutarConsultaInicio(inputInicio.value);
    });
  }

  async function ejecutarConsultaInicio(termino) {
    const query = (termino || "").trim();
    if (!validarEntrada(query, inputInicio)) return;

    if (inputInicio.value !== query) {
      inputInicio.value = query;
    }

    if (btnSubmitInicio) btnSubmitInicio.disabled = true;
    if (spinnerInicio) spinnerInicio.classList.remove("d-none");
    if (btnTextInicio) btnTextInicio.textContent = "Buscando...";

    if (secCargando) secCargando.classList.remove("d-none");
    if (secVacio) secVacio.classList.add("d-none");
    if (secResultado) secResultado.classList.add("d-none");

    try {
      const response = await fetch(`/api/v1/tandeos/buscar?q=${encodeURIComponent(query)}`);
      const data = await response.json();

      if (!response.ok || !data.encontrado) {
        if (vacioTitulo) vacioTitulo.textContent = "No encontramos esa colonia o código postal";
        if (vacioMensaje) {
          vacioMensaje.textContent = data.mensaje || "Por favor verifique la ortografía o intente con el código postal.";
        }
        if (secCargando) secCargando.classList.add("d-none");
        if (secVacio) secVacio.classList.remove("d-none");
        return;
      }

      // Llenar Ficha de Colonia
      if (resColonia) resColonia.textContent = data.colonia.nombre || data.colonia.nombre_colonia;
      if (resCodigoPostal) resCodigoPostal.textContent = `C.P. ${data.colonia.codigo_postal}`;
      if (resSector) resSector.textContent = data.sector ? (data.sector.nombre || data.sector.nombre_sector) : "Sector Asignado";
      if (resRed) resRed.textContent = `Red: ${data.sector ? (data.sector.descripcion || data.sector.red_hidraulica || "Red General") : "Red General"}`;

      if (resDisponibilidad && data.fiabilidad) {
        resDisponibilidad.innerHTML = `
          <span class="badge bg-${data.fiabilidad.badge_clase}-subtle text-${data.fiabilidad.badge_clase}-emphasis border border-${data.fiabilidad.badge_clase}-subtle px-3 py-2 fs-6 rounded-pill">
            <i class="bi bi-shield-check me-1"></i>${data.fiabilidad.nivel_estabilidad} (${data.fiabilidad.porcentaje_cobertura}%)
          </span>
        `;
      }

      // Llenar Calendario Semanal
      if (gridCalendario) {
        gridCalendario.innerHTML = "";
        const prog = data.programacion || [];

        if (prog.length === 0) {
          gridCalendario.innerHTML = '<div class="col-12 py-4 text-center text-muted">Actualmente no existe programación disponible para esta zona.</div>';
        } else {
          prog.forEach((item) => {
            const esHoy = normalizar(item.dia_semana) === normalizar(diaHoyNombre);
            const est = (item.estado_servicio || "").toLowerCase();
            const card = document.createElement("div");
            card.className = `day-schedule-card status-${est} ${esHoy ? "today" : ""}`;

            let badgeHtml = "";
            let horaHtml = "";

            if (item.estado_servicio === "Activo") {
              badgeHtml = '<span class="badge badge-status-activo px-2 py-1 w-100"><i class="bi bi-droplet-fill me-1"></i>Servicio Suministrado</span>';
              horaHtml = `<i class="bi bi-clock me-1 text-success"></i>${item.hora_inicio} - ${item.hora_fin} hrs`;
            } else if (item.estado_servicio === "Mantenimiento") {
              badgeHtml = '<span class="badge badge-status-mantenimiento px-2 py-1 w-100"><i class="bi bi-tools me-1"></i>Mantenimiento en Red</span>';
              horaHtml = `<i class="bi bi-clock-history me-1 text-warning"></i>${item.hora_inicio} - ${item.hora_fin} hrs`;
            } else {
              badgeHtml = '<span class="badge badge-status-suspendido px-2 py-1 w-100"><i class="bi bi-slash-circle me-1"></i>Corte por Tandeo</span>';
              horaHtml = '<span class="text-danger fw-semibold"><i class="bi bi-x-circle me-1"></i>Sin servicio</span>';
            }

            card.innerHTML = `
              <div>
                <div class="d-flex align-items-center justify-content-between mb-1">
                  <span class="day-title">${item.dia_semana}</span>
                  ${esHoy ? '<span class="badge bg-primary text-white small px-2 py-0">Hoy</span>' : ""}
                </div>
                <div>${badgeHtml}</div>
              </div>
              <div class="schedule-hours mt-3">${horaHtml}</div>
            `;
            gridCalendario.appendChild(card);
          });
        }
      }

      // Coincidencias alternativas
      if (secCoincidencias && listaCoincidencias) {
        const coincidencias = (data.coincidencias || []).filter(
          (c) => c.id_colonia !== data.colonia.id_colonia
        );

        if (coincidencias.length > 0) {
          listaCoincidencias.innerHTML = "";
          coincidencias.forEach((col) => {
            const nom = col.nombre || col.nombre_colonia;
            const pill = document.createElement("a");
            pill.href = `/consulta?q=${encodeURIComponent(nom)}`;
            pill.className = "btn-suggestion-tag";
            pill.textContent = `${nom} (C.P. ${col.codigo_postal})`;
            listaCoincidencias.appendChild(pill);
          });
          secCoincidencias.classList.remove("d-none");
        } else {
          secCoincidencias.classList.add("d-none");
        }
      }

      if (secCargando) secCargando.classList.add("d-none");
      if (secResultado) {
        secResultado.classList.remove("d-none");
        secResultado.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch (err) {
      console.error("Error en consulta:", err);
      if (vacioTitulo) vacioTitulo.textContent = "Error de conexión temporal";
      if (vacioMensaje) vacioMensaje.textContent = "No fue posible conectar con el servicio. Por favor intente más tarde.";
      if (secCargando) secCargando.classList.add("d-none");
      if (secVacio) secVacio.classList.remove("d-none");
    } finally {
      if (btnSubmitInicio) btnSubmitInicio.disabled = false;
      if (spinnerInicio) spinnerInicio.classList.add("d-none");
      if (btnTextInicio) btnTextInicio.textContent = "Consultar";
    }
  }

  // =========================================================================
  // 4. PÁGINA CALENDARIO (/consulta): AUTOCOMPLETADO Y VALIDACIÓN
  // =========================================================================
  if (formCalendario && inputCalendario) {
    conectarAutocompletado(inputCalendario, (nombreColonia) => {
      inputCalendario.value = nombreColonia;
      formCalendario.submit();
    });

    formCalendario.addEventListener("submit", (e) => {
      if (!validarEntrada(inputCalendario.value, inputCalendario)) {
        e.preventDefault();
      }
    });
  }

  // Sugerencias rápidas predefinidas (.js-sugerencia-tag)
  document.querySelectorAll(".js-sugerencia-tag").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const val = btn.getAttribute("data-query");
      if (inputInicio) {
        inputInicio.value = val;
        ejecutarConsultaInicio(val);
      } else if (inputCalendario && formCalendario) {
        inputCalendario.value = val;
        formCalendario.submit();
      }
    });
  });
})();
