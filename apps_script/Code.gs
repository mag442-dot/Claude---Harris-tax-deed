/**
 * Webhook que recibe el CSV del repo y lo escribe en la pestaña "Analisis" de ESTE Sheet.
 * Se pega en Extensiones > Apps Script. Ver apps_script/README.md.
 * Seguridad: solo acepta POST con el TOKEN guardado en Propiedades del script.
 */
var DEFAULT_TAB = 'Analisis';
var TEXT_COLS = ['property_id', 'account_no', 'cuenta'];   // se guardan como texto para no perder ceros iniciales

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    var token = PropertiesService.getScriptProperties().getProperty('TOKEN');
    if (!token || body.token !== token) return out_({ ok: false, error: 'unauthorized' });
    if (!body.csv) return out_({ ok: false, error: 'missing csv' });

    var rows = Utilities.parseCsv(body.csv);
    rows = rows.filter(function (r) { return r.join('') !== ''; });
    if (rows.length < 2) return out_({ ok: false, error: 'csv has no data rows' });
    var width = rows[0].length;
    rows = rows.map(function (r) {
      var row = r.slice(0, width);
      while (row.length < width) row.push('');
      return row.map(function (c) { return /^[=+\-@]/.test(c) && isNaN(Number(c)) ? "'" + c : c; });  // evita formulas inyectadas
    });

    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var name = body.sheet || DEFAULT_TAB;
    var sh = ss.getSheetByName(name) || ss.insertSheet(name);
    sh.clearContents();
    sh.clearFormats();
    rows[0].forEach(function (h, i) {
      if (TEXT_COLS.indexOf(h) >= 0) sh.getRange(1, i + 1, rows.length, 1).setNumberFormat('@');
    });
    sh.getRange(1, 1, rows.length, width).setValues(rows);
    sh.getRange(1, 1, 1, width).setFontWeight('bold').setBackground('#e8eaed');
    sh.setFrozenRows(1);
    sh.autoResizeColumns(1, Math.min(width, 10));

    var info = ss.getSheetByName('Info') || ss.insertSheet('Info');
    info.getRange('A1:B3').setValues([
      ['Ultima actualizacion', new Date()],
      ['Filas de datos', rows.length - 1],
      ['Origen', body.source || 'repo']
    ]);
    return out_({ ok: true, rows: rows.length - 1, sheet: name });
  } catch (err) {
    return out_({ ok: false, error: String(err) });
  }
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
