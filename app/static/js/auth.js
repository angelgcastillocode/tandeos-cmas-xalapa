(() => {
  "use strict";

  const form = document.getElementById("loginForm");
  const correoInput = document.getElementById("correo");
  const passwordInput = document.getElementById("password");
  const toggleBtn = document.getElementById("togglePassword");
  const toggleIcon = document.getElementById("togglePasswordIcon");
  const submitBtn = document.getElementById("btnLogin");
  const submitText = document.getElementById("btnLoginText");
  const spinner = document.getElementById("loginSpinner");

  // Mostrar / ocultar contraseña con icono interactivo
  if (toggleBtn && passwordInput && toggleIcon) {
    toggleBtn.addEventListener("click", () => {
      const isPassword = passwordInput.type === "password";
      passwordInput.type = isPassword ? "text" : "password";

      toggleBtn.setAttribute("aria-pressed", String(isPassword));
      toggleBtn.setAttribute(
        "aria-label",
        isPassword ? "Ocultar contraseña" : "Mostrar contraseña"
      );

      if (isPassword) {
        toggleIcon.classList.remove("bi-eye");
        toggleIcon.classList.add("bi-eye-slash");
      } else {
        toggleIcon.classList.remove("bi-eye-slash");
        toggleIcon.classList.add("bi-eye");
      }

      passwordInput.focus();
    });
  }

  // Validación y estado de carga en el envío
  if (form && submitBtn && submitText && spinner) {
    form.addEventListener("submit", (e) => {
      if (!form.checkValidity()) {
        e.preventDefault();
        e.stopPropagation();
        form.classList.add("was-validated");
        return;
      }

      // Activar estado de carga en botón
      submitBtn.disabled = true;
      spinner.classList.remove("d-none");
      submitText.textContent = "Iniciando sesión...";
    });
  }

  // Auto-cierre progresivo de mensajes flash
  document.querySelectorAll(".flash-container .alert").forEach((alertEl) => {
    setTimeout(() => {
      alertEl.classList.add("fade");
      setTimeout(() => {
        if (alertEl.parentNode) {
          alertEl.remove();
        }
      }, 350);
    }, 5000);
  });
})();