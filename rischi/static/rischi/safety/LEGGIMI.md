# Motore di calcolo PL

`engine.js` e `schema.js` sono copie identiche dei file di `cosmap-safety-evaluation/safety-eval/`
(commit c080e8a). Si correggono qui e là insieme finché la safety evaluation non viene dismessa (fase 6).

- `valutazione.js`: interfaccia della pagina "Calcolo PL" (schema a blocchi, componenti, calcolo, verifica),
  ricavata dai passi 2-5 della safety evaluation.
- `calcola.js`: lo stesso motore eseguito con Node dal server (`rischi/calcolo.py`), così i risultati salvati
  non dipendono da quelli inviati dal browser.
