// Archivio articoli di partenza. Ogni valore deve avere una fonte: se manca, il campo resta null.
// PFH in 10⁻⁹/h, B10d in cicli, MTTFd in anni. "verificato" = confrontato con il documento originale.
(function (root) {
  const SIEMENS = 'Siemens, "Probability of failure Safety Integrated SINAMICS", Entry-ID 76254308 V2.1 (04/2024)';
  const NOTA = 'Valore riportato nel CLAUDE.md del calcolatore, da confrontare con il PDF. Validità subordinata al test diagnostico previsto dai manuali.';
  const s120 = (id, codice, descrizione, pfh) => ({
    id, codice, descrizione, produttore: 'Siemens', tipo: 'attuatore', pfh, b10d: null, mttfd: null,
    plMax: null, fonte: SIEMENS, dataFonte: '2024-04', verificato: false, note: NOTA,
  });
  const ARTICOLI = [
    s120('s120-cu320-2pn', 'CU320-2 PN', 'SINAMICS S120 Control Unit', 10),
    s120('s120-smm', 'S120 SMM booksize', 'Motor Module singolo, STO/SS1', 10),
    s120('s120-smm-sbc', 'S120 SMM booksize + SBC', 'Motor Module singolo con SBC', 14),
    s120('s120-dmm', 'S120 DMM booksize', 'Motor Module doppio, 2 assi usati', 12),
    s120('s120-dmm-sbc', 'S120 DMM booksize + SBC', 'Motor Module doppio, SBC su 2 assi', 20),
    s120('s120-dmm-sbc1', 'S120 DMM booksize + SBC 1 asse', 'Motor Module doppio, SBC su 1 asse', 16),
    s120('s120-sensorless', 'S120 monitoraggio senza encoder', 'Monitoraggio senza encoder, booksize', 5),
  ];
  if (typeof module !== 'undefined' && module.exports) module.exports = ARTICOLI;
  else root.ARTICOLI_DEFAULT = ARTICOLI;
})(typeof self !== 'undefined' ? self : this);
