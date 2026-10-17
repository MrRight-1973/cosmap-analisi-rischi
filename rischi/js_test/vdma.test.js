// node --test safety-eval/test/vdma.test.js
// Database VDMA 66413 sintetico con la stessa struttura di quelli dei costruttori.
const test = require('node:test');
const assert = require('node:assert/strict');
const { importa, importaPacchetto, parseXml, FormatError } = require('../static/rischi/safety/vdma.js');
const { apri } = require('../static/rischi/safety/zip.js');

const T = (k, de, en) => `<X Key="${k}"><Text LanguageKey="de">${de}</Text><Text LanguageKey="en">${en}</Text></X>`;
const sez = (nome, el, voci) => `<${nome}>${voci.map(v => T(...v).replace(/X/g, el)).join('')}</${nome}>`;
const uc = (fn, cat, par, cons = '<Hierarchy1 Key="#NotApplicable" />') => `<UseCase><Constraints>${cons}</Constraints><Function>
  <InputFunction>${fn === 'i'}</InputFunction><LogicFunction>${fn === 'l'}</LogicFunction><OutputFunction>${fn === 'o'}</OutputFunction></Function>
  <InfoConfig>CAT_${cat}</InfoConfig><Parameter>${par}</Parameter></UseCase>`;
const dev = (id, n, pn, ucs, extra = '') => `<Device><Identifier>${id}</Identifier><Group Key="Group_1" /><Name Key="Type_${n}" />
  <PartNumber>${pn}</PartNumber>${extra}<Archive>false</Archive><UseCases>${ucs.join('')}</UseCases></Device>`;
const XML = `﻿<?xml version="1.0" encoding="utf-8"?>
<VDMA66413 Version="1.0.0"><Manufacturer Version="2.1"><Name>ACME AG</Name><DBFileName>vdma.xml</DBFileName>
<Language>${sez('Groups', 'Group', [['Group_1', 'Gruppe', 'Drives &amp; Co']])}
${sez('Names', 'Name', [['Type_1', 'Antrieb', 'Drive 1'], ['Type_2', 'Schalter', 'Switch'], ['Type_3', 'Taster', 'Button'], ['Type_4', 'Leer', 'Empty']])}
${sez('Constraints', 'Constraint', [['Constraint_1', 'PROFIsafe', 'PROFIsafe'], ['Constraint_2', 'Klemmen', 'terminals']])}
${sez('DocFiles', 'DocFile', [['Doc_1', 'http://x/de.pdf', 'http://x/en.pdf']])}</Language>
<Devices>
${dev('Antrieb | A1', 1, ' 6SL-1 ', [
    uc('o', 4, '<DeviceType1><PL>PL_e</PL><SILCL>SIL_3</SILCL><PFH_d>1,2E-08</PFH_d><TM_T1>20,0</TM_T1></DeviceType1>', '<Hierarchy1 Key="Constraint_1" />'),
    uc('o', 3, '<DeviceType1><PL>PL_d</PL><PFH_d>3E-08</PFH_d><TM_T1>20,0</TM_T1></DeviceType1>', '<Hierarchy1 Key="Constraint_2" />')], '<DocFile Key="Doc_1" /><IconFileName>P_Drive.PNG</IconFileName>')}
${dev('Schalter | S1', 2, '3SE', [uc('i', 'na', '<DeviceType3><B10>1000000</B10><RDF>20</RDF><TM_T1>20,0</TM_T1></DeviceType3>')])}
${dev('Taster | T1', 3, '3SU', [uc('i', 'na', '<DeviceType2><MTTF>535,0</MTTF><RDF>50</RDF><TM_T1>20,0</TM_T1></DeviceType2>'),
    uc('i', 'na', '<DeviceType3><B10d>6000000</B10d><RDF>100</RDF></DeviceType3>')])}
${dev('Leer | L1', 4, 'X', [uc('l', 'na', '<DeviceType1><PL>PL_e</PL><TM_T1>20,0</TM_T1></DeviceType1>')])}
</Devices></Manufacturer></VDMA66413>`;

test('parseXml: attributi, entità, elementi vuoti', () => {
  const d = parseXml('<a x="1 &amp; 2"><b/><c>&lt;ok&gt; &#65;</c></a>');
  assert.equal(d.children[0].attrs.x, '1 & 2');
  assert.equal(d.children[0].children[1].text, '<ok> A');
  assert.throws(() => parseXml('<a><b></a>'), FormatError);
});

test('importa: un articolo per use case, valori e fonte', () => {
  const r = importa(XML);
  assert.equal(r.libreria, 'ACME AG · VDMA vdma.xml 2.1');
  assert.deepEqual(r.articoli.map(a => [a.codice, a.tipo, a.pfh, a.plMax, a.b10d, a.mttfd]), [
    ['6SL-1', 'attuatore', 12, 'e', null, null],
    ['6SL-1', 'attuatore', 30, 'd', null, null],
    ['3SE', 'sensore', null, null, 5000000, null], // B10 / RDF = 1e6 / 20 %
    ['3SU', 'sensore', null, null, null, 1070], // MTTF / RDF = 535 / 50 %
    ['3SU', 'sensore', null, null, 6000000, null],
  ]);
  const [a1, a2, s] = r.articoli;
  assert.equal(a1.descrizione, 'Drive 1 · PROFIsafe');
  assert.equal(a2.descrizione, 'Drive 1 · terminals');
  assert.equal(a1.gruppo, 'Drives & Co');
  assert.equal(a1.fonte, 'ACME AG, database VDMA 66413 "vdma.xml" versione 2.1, "Antrieb | A1" use case 1, cat. 4, mission time 20 anni; documentazione: http://x/en.pdf');
  assert.match(s.fonte, /B10d = B10 \/ RDF = 1000000 \/ 20 %/);
  assert.ok(r.articoli.every(a => a.produttore === 'ACME AG' && a.verificato === false));
  assert.equal(new Set(r.articoli.map(a => a.id)).size, 5);
  assert.deepEqual(r.scartati, [['use case 1 senza PFH, B10d o MTTFd', 'Empty']]);
});

test('id stabili tra due import', () => {
  assert.deepEqual(importa(XML).articoli.map(a => a.id), importa(XML).articoli.map(a => a.id));
});

test('file che non è VDMA 66413 → FormatError', () => {
  assert.throws(() => importa('<?xml version="1.0"?><altro/>'), FormatError);
});

test('importaPacchetto: database e immagini dallo .zip', async () => {
  const { creaZip } = require('./crea-zip.js');
  const png = Uint8Array.from([0x89, 0x50, 0x4e, 0x47, 1, 2, 3]);
  const zip = creaZip([{ nome: 'leggimi.xml', dati: '<altro/>' }, { nome: 'pkg/vdma.xml', dati: XML, deflate: true }, { nome: 'pkg/PNG/p_drive.png', dati: png }]);
  const r = await importaPacchetto(apri(zip));
  assert.equal(r.file, 'pkg/vdma.xml');
  assert.equal(r.articoli.length, 5);
  assert.deepEqual(r.articoli.map(a => a.immagine || null), ['acme/p_drive.png', 'acme/p_drive.png', null, null, null]);
  assert.deepEqual([...r.immagini.keys()], ['acme/p_drive.png']);
  assert.deepEqual([...r.immagini.get('acme/p_drive.png').byte], [...png]);
  assert.equal(r.immagini.get('acme/p_drive.png').tipo, 'image/png');
  assert.equal(r.immaginiMancanti, 0);
});

test('importaPacchetto: zip senza database VDMA → FormatError', async () => {
  const { creaZip } = require('./crea-zip.js');
  await assert.rejects(importaPacchetto(apri(creaZip([{ nome: 'x.txt', dati: 'x' }]))), FormatError);
});
