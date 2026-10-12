// Confere o porte JS contra o gabarito gerado pelo Python (nível e motivos), em todas as vagas.
// Uso: node catalogo/simulador/conferir.js gabarito-py.json
const fs = require("fs"), path = require("path");
const C = require("./casamento.js");
const cat = new C.Catalogo(JSON.parse(fs.readFileSync(path.join(__dirname, "dados/catalogo.json"), "utf8")));
const dados = JSON.parse(fs.readFileSync(path.join(__dirname, "dados/vagas.json"), "utf8"));
const g = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
let n = 0, dif = 0, difMot = 0;
for (const p of g.perfis) {
  for (const v of dados.vagas) {
    const [r] = C.avaliarVaga(cat, v, p); n++;
    const [nivel, motivos] = g.gabarito[p.id][v.concurso + "|" + v.vaga];
    if (r.nivel !== nivel) { dif++; if (dif <= 10) console.log("NIVEL", p.id, v.concurso, v.vaga, nivel, "->", r.nivel, r.motivos); }
    else if (JSON.stringify(r.motivos) !== JSON.stringify(motivos)) { difMot++; if (difMot <= 5) console.log("MOTIVO", p.id, v.concurso, v.vaga, motivos, r.motivos); }
  }
}
console.log(`comparações: ${n}, níveis diferentes: ${dif}, motivos diferentes: ${difMot}`);
process.exit(dif ? 1 : 0);
