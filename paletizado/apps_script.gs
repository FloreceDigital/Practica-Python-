/**
 * Apps Script para recibir las tarimas en Google Sheets.
 *
 * Cómo instalarlo (una sola vez):
 *  1. Abre la hoja de Google Sheets de la empresa.
 *  2. Menú Extensiones > Apps Script.
 *  3. Borra lo que haya y pega todo este archivo.
 *  4. Cambia CLAVE por una palabra secreta (la misma que pondrás en config.py).
 *  5. Guardar. Luego: Implementar > Nueva implementación > tipo "Aplicación web".
 *       - Ejecutar como: Yo
 *       - Quién tiene acceso: Cualquier usuario
 *  6. Autoriza los permisos y copia la URL que termina en /exec.
 *     Esa URL va en config.py como SHEETS_URL.
 */

const CLAVE = "cambia-esta-clave";
const NOMBRE_HOJA = "Tarimas";

// [clave que manda la app, título de la columna en la hoja]
// Los primeros títulos son los mismos del formulario de Google que usaban antes.
const COLUMNAS = [
  ["fecha", "Fecha"], ["turno", "Shift"], ["producto", "Product"], ["color", "Color"],
  ["lote", "Lot No."], ["numero_pallet", "Finished Pallet No."],
  ["fardos", "Count of bales per Pallet"], ["libras", "Weight (Lb)"],
  ["lote_film", "Lot Packaging Material / Bag film"], ["lote_bale", "Lot Packaging Material / Bale"],
  ["operador_produccion", "Production Operator"], ["montacarguista", "Forklift Operator"],
  ["supervisor", "Shift Supervisor"], ["estibadores", "Estibador"], ["comentarios", "Comentarios"],
  ["hora", "Hora"], ["linea", "Línea"], ["folio", "Folio"], ["bolsas", "Bolsas"],
  ["completa", "Completa"], ["estado", "Estado"],
];
const CLAVES = COLUMNAS.map((c) => c[0]);
const COL_FOLIO = CLAVES.indexOf("folio") + 1;
const COL_ESTADO = CLAVES.indexOf("estado") + 1;

function doPost(e) {
  const datos = JSON.parse(e.postData.contents);
  if (datos.clave !== CLAVE) return responder({ ok: false, error: "clave incorrecta" });

  const candado = LockService.getScriptLock();
  candado.waitLock(20000);
  try {
    const hoja = obtenerHoja();
    if (datos.accion === "agregar") {
      // Si el folio ya existe (reenvío), no se duplica.
      if (buscarFila(hoja, datos.tarima.folio) === -1) {
        hoja.appendRow(CLAVES.map((c) => datos.tarima[c] ?? ""));
      }
    } else if (datos.accion === "anular") {
      const fila = buscarFila(hoja, datos.folio);
      if (fila !== -1) {
        hoja.getRange(fila, COL_ESTADO).setValue("ANULADA");
        hoja.getRange(fila, 1, 1, COLUMNAS.length).setBackground("#f8cbad");
      }
    }
    return responder({ ok: true });
  } finally {
    candado.releaseLock();
  }
}

function obtenerHoja() {
  const libro = SpreadsheetApp.getActiveSpreadsheet();
  let hoja = libro.getSheetByName(NOMBRE_HOJA);
  if (!hoja) {
    hoja = libro.insertSheet(NOMBRE_HOJA);
    hoja.appendRow(COLUMNAS.map((c) => c[1]));
    hoja.getRange(1, 1, 1, COLUMNAS.length)
      .setFontWeight("bold").setFontColor("#ffffff").setBackground("#1f4e78");
    hoja.setFrozenRows(1);
  }
  return hoja;
}

function buscarFila(hoja, folio) {
  const ultima = hoja.getLastRow();
  if (ultima < 2) return -1;
  const folios = hoja.getRange(2, COL_FOLIO, ultima - 1, 1).getValues();
  for (let i = folios.length - 1; i >= 0; i--) {
    if (folios[i][0] === folio) return i + 2;
  }
  return -1;
}

function responder(objeto) {
  return ContentService.createTextOutput(JSON.stringify(objeto))
    .setMimeType(ContentService.MimeType.JSON);
}
