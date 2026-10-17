# Motore di calcolo PL

`engine.js`, `schema.js` e `validazione.js` sono copie identiche dei file di `cosmap-safety-evaluation/safety-eval/`
(commit c080e8a). Si correggono qui e là insieme finché la safety evaluation non viene dismessa (fase 6).

- `valutazione.js`: interfaccia della pagina "Calcolo PL" (schema a blocchi, componenti, calcolo, verifica),
  ricavata dai passi 2-5 della safety evaluation.
- `validazione-pagina.js`: pagine della validazione (prove di una funzione, misure contro i guasti sistematici),
  ricavate dal passo 6 della safety evaluation.
- `verifiche-pagina.js`: pagina delle verifiche elettriche (prove EN 60204-1 cap. 18, registro misure con
  incolla da Excel), ricavata dal passo 6 della safety evaluation.
- `calcola.js`: lo stesso motore eseguito con Node dal server (`rischi/calcolo.py`), così i risultati salvati
  non dipendono da quelli inviati dal browser. Per la relazione e la validazione calcola più funzioni insieme e
  restituisce anche schema, sottosistemi, prove standard e misure contro i guasti sistematici; per le verifiche
  elettriche restituisce prove, riepilogo, registro ed esito dell'isolamento di ogni cavo.
