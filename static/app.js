/* Analizador Web Grupodot — front de demo, JS vanilla. */

const $ = (id) => document.getElementById(id);

const form = $("form");
const inputUrl = $("url");
const btn = $("btn");
const loader = $("loader");
const progreso = $("progreso");
const progresoUrl = $("progreso-url");
const cajaError = $("error");
const errorMsg = $("error-msg");
const resultado = $("resultado");

// Si no existe logo-dot.png en la raíz, el <img> falla y mostramos el wordmark.
$("logo").addEventListener("error", () => {
  $("logo").classList.add("oculto");
  $("wordmark").classList.remove("oculto");
});

// --- Loader por fases -------------------------------------------------------
// Una sola petición cubre las 3 fases, así que el mensaje avanza por tiempo
// estimado. Los tiempos reflejan la duración típica de cada fase.
const FASES = [
  { t: 0, msg: "Escaneando sitio..." },
  { t: 6000, msg: "Generando análisis con IA..." },
  { t: 40000, msg: "Creando presentación..." },
];

let temporizadores = [];

function iniciarProgreso(url) {
  progresoUrl.textContent = url;
  temporizadores = FASES.map((f) =>
    setTimeout(() => {
      progreso.textContent = f.msg;
    }, f.t)
  );
}

function detenerProgreso() {
  temporizadores.forEach(clearTimeout);
  temporizadores = [];
}

// --- Render -----------------------------------------------------------------

const CLASE_PRIORIDAD = {
  Inmediata: "p-inmediata",
  "Corto plazo": "p-corto",
  "Mediano plazo": "p-mediano",
};

function mostrarResultado(data) {
  $("r-url").textContent = data.url;

  const sector = data.sector || {};
  const partesSector = [sector.industria, sector.subsector].filter(Boolean);
  $("r-sector").textContent = partesSector.join(" · ");

  const madurez = data.madurez || {};
  $("r-score").textContent = madurez.score ?? "–";
  $("r-nivel").textContent = madurez.nivel || "Sin nivel";
  $("r-resumen").textContent = data.resumen_ejecutivo || "Sin resumen disponible.";

  // Servicios recomendados
  const servicios = data.servicios_recomendados || [];
  const ulServicios = $("r-servicios");
  ulServicios.innerHTML = "";
  servicios.forEach((s) => {
    const li = document.createElement("li");

    const nombre = document.createElement("span");
    nombre.className = "srv-nombre";
    nombre.textContent = s.servicio || "";
    li.appendChild(nombre);

    if (s.prioridad) {
      const pill = document.createElement("span");
      pill.className = "srv-prioridad " + (CLASE_PRIORIDAD[s.prioridad] || "");
      pill.textContent = s.prioridad;
      li.appendChild(pill);
    }

    if (s.descripcion) {
      const desc = document.createElement("p");
      desc.className = "srv-desc";
      desc.textContent = s.descripcion;
      li.appendChild(desc);
    }

    ulServicios.appendChild(li);
  });
  $("bloque-servicios").classList.toggle("oculto", servicios.length === 0);

  // Quick wins
  const quickWins = data.quick_wins || [];
  const ulQuick = $("r-quickwins");
  ulQuick.innerHTML = "";
  quickWins.forEach((q) => {
    const li = document.createElement("li");
    li.textContent = q;
    ulQuick.appendChild(li);
  });
  $("bloque-quickwins").classList.toggle("oculto", quickWins.length === 0);

  $("r-descarga").href = data.pptx.descarga;
  $("r-tiempo").textContent = `Generado en ${data.duracion_segundos} s`;

  resultado.classList.remove("oculto");
  resultado.scrollIntoView({ behavior: "smooth", block: "start" });
}

function mostrarError(mensaje) {
  errorMsg.textContent = mensaje;
  cajaError.classList.remove("oculto");
}

// --- Historial --------------------------------------------------------------

const hLista = $("h-lista");
const hEstado = $("h-estado");
const hTotal = $("h-total");

const CLASE_NIVEL = {
  Inexistente: "n-basico",
  "Básico": "n-basico",
  Intermedio: "n-intermedio",
  Avanzado: "n-avanzado",
  "Líder": "n-lider",
};

function formatearFecha(iso) {
  if (!iso) return "Fecha desconocida";
  const d = new Date(iso);
  if (isNaN(d)) return "Fecha desconocida";
  return d.toLocaleDateString("es-CO", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function crearTarjetaHistorial(item) {
  const fila = document.createElement("div");
  fila.className = "h-item";
  fila.dataset.dominio = item.dominio;

  // Score
  const madurez = item.madurez || {};
  const score = document.createElement("div");
  score.className = "h-score " + (CLASE_NIVEL[madurez.nivel] || "n-sindato");
  score.textContent = madurez.score ?? "–";
  score.title = madurez.nivel || "Análisis incompleto";
  fila.appendChild(score);

  // Datos: dominio + línea meta
  const datos = document.createElement("div");
  datos.className = "h-datos";

  const titulo = document.createElement("p");
  titulo.className = "h-dominio";
  // El dominio guardado usa "_" en vez de "."; mostramos la URL real si la hay.
  titulo.textContent = item.url || item.dominio.replace(/_/g, ".");
  datos.appendChild(titulo);

  const meta = document.createElement("p");
  meta.className = "h-meta";
  const partes = [
    madurez.nivel,
    (item.sector || {}).industria,
    formatearFecha(item.fecha),
  ].filter(Boolean);
  if (!item.archivos.analisis) partes.unshift("Análisis incompleto");
  meta.textContent = partes.join(" · ");
  datos.appendChild(meta);

  fila.appendChild(datos);

  // Acciones
  const acciones = document.createElement("div");
  acciones.className = "h-acciones";

  const descarga = document.createElement("a");
  descarga.className = "h-btn";
  descarga.textContent = "Descargar PPTX";
  if (item.descarga) {
    descarga.href = item.descarga;
  } else {
    descarga.classList.add("deshabilitado");
    descarga.title = "No hay presentación generada para este dominio.";
  }
  acciones.appendChild(descarga);

  const eliminar = document.createElement("button");
  eliminar.type = "button";
  eliminar.className = "h-btn h-eliminar";
  eliminar.textContent = "Eliminar";
  eliminar.addEventListener("click", () => eliminarAnalisis(item, fila, eliminar));
  acciones.appendChild(eliminar);

  fila.appendChild(acciones);
  return fila;
}

function pintarHistorial(items) {
  hLista.innerHTML = "";

  if (items.length === 0) {
    hEstado.classList.add("oculto");
    hTotal.textContent = "";
    const vacio = document.createElement("p");
    vacio.className = "historial-vacio";
    vacio.textContent = "Todavía no hay análisis guardados. Analiza un sitio para empezar.";
    hLista.appendChild(vacio);
    return;
  }

  hEstado.classList.add("oculto");
  hTotal.textContent = items.length === 1 ? "1 sitio" : `${items.length} sitios`;
  items.forEach((item) => hLista.appendChild(crearTarjetaHistorial(item)));
}

async function cargarHistorial() {
  try {
    const resp = await fetch("/historial");
    if (!resp.ok) throw new Error(`Error ${resp.status}`);
    const data = await resp.json();
    pintarHistorial(data.analisis || []);
  } catch (err) {
    hLista.innerHTML = "";
    hTotal.textContent = "";
    hEstado.classList.remove("oculto");
    hEstado.textContent = "No se pudo cargar el historial.";
  }
}

async function eliminarAnalisis(item, fila, boton) {
  const nombre = item.url || item.dominio.replace(/_/g, ".");
  const ok = confirm(
    `¿Eliminar el análisis de ${nombre}?\n\n` +
      "Se borrarán el diagnóstico, el análisis y la presentación .pptx.\n" +
      "Esta acción no se puede deshacer."
  );
  if (!ok) return;

  boton.disabled = true;
  boton.textContent = "Eliminando...";

  try {
    const resp = await fetch(`/historial/${encodeURIComponent(item.dominio)}`, {
      method: "DELETE",
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `Error ${resp.status}`);

    // Quita solo esta tarjeta, sin recargar la lista completa.
    fila.classList.add("saliendo");
    setTimeout(() => {
      fila.remove();
      const quedan = hLista.querySelectorAll(".h-item").length;
      if (quedan === 0) pintarHistorial([]);
      else hTotal.textContent = quedan === 1 ? "1 sitio" : `${quedan} sitios`;
    }, 200);
  } catch (err) {
    alert(`No se pudo eliminar: ${err.message}`);
    boton.disabled = false;
    boton.textContent = "Eliminar";
  }
}

document.addEventListener("DOMContentLoaded", cargarHistorial);

// --- Envío ------------------------------------------------------------------

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const url = inputUrl.value.trim();
  if (!url) return;

  resultado.classList.add("oculto");
  cajaError.classList.add("oculto");
  loader.classList.remove("oculto");
  btn.disabled = true;
  btn.textContent = "Analizando...";
  progreso.textContent = FASES[0].msg;
  iniciarProgreso(url);

  try {
    const resp = await fetch("/analizar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const data = await resp.json().catch(() => ({}));

    if (!resp.ok) {
      throw new Error(data.detail || `Error ${resp.status} del servidor.`);
    }

    mostrarResultado(data);
    // El análisis nuevo ya está en disco: refrescamos la lista sin recargar.
    cargarHistorial();
  } catch (err) {
    mostrarError(err.message || "Error de red: ¿está corriendo el servidor?");
  } finally {
    detenerProgreso();
    loader.classList.add("oculto");
    btn.disabled = false;
    btn.textContent = "Analizar";
  }
});
