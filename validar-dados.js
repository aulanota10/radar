// Validador do dados.js do Radar de Concursos · Aula Nota 10
// Roda no GitHub Actions antes de publicar. Se falhar, o deploy nao acontece.
// Uso local: node validar-dados.js
const path = require('path');
global.window = {};
const arquivo = path.resolve(__dirname, 'dados.js');
try {
  require(arquivo);
} catch (e) {
  console.error('ERRO DE SINTAXE: o dados.js nao carrega em node.');
  console.error(e.message);
  process.exit(1);
}

const c = window.CONCURSOS;
const erros = [];
const avisos = [];

if (!Array.isArray(c)) {
  console.error('ERRO: window.CONCURSOS nao e um array.');
  process.exit(1);
}

const re = /^\d{4}-\d{2}-\d{2}$/;
const TIPOS_DATA = ['exata', 'periodo', 'nao_divulgada'];
const TIPOS_ETAPA = ['objetiva', 'discursiva', 'didatica', 'titulos', 'memorial', 'resultado', 'outra'];
const SITUACOES = ['aberta', 'abre_em_breve', 'encerrada', 'consultar'];

const ids = c.map(x => x.id);
ids.filter((v, i) => ids.indexOf(v) !== i)
   .forEach(d => erros.push('id duplicado: ' + d));

c.forEach((x, i) => {
  const ref = x.id || ('posicao ' + (i + 1));
  if (!x.id) erros.push('concurso sem id na posicao ' + (i + 1));
  if (!x.sigla) avisos.push(ref + ': sem sigla');
  if (!x.link_oficial) avisos.push(ref + ': sem link_oficial');

  const etapas = x.etapas || [];
  if (!etapas.some(e => e.tipo === 'didatica')) {
    erros.push(ref + ': nenhuma etapa com tipo "didatica"');
  }

  const ins = x.inscricao || {};
  ['inicio', 'fim'].forEach(k => {
    if (ins[k] && !re.test(ins[k])) erros.push(ref + ': inscricao.' + k + ' fora do formato AAAA-MM-DD -> ' + ins[k]);
  });
  if (ins.situacao && !SITUACOES.includes(ins.situacao)) {
    erros.push(ref + ': inscricao.situacao invalida -> ' + ins.situacao);
  }
  if (ins.inicio && ins.fim && re.test(ins.inicio) && re.test(ins.fim) && ins.fim < ins.inicio) {
    erros.push(ref + ': inscricao termina antes de comecar');
  }

  etapas.forEach(e => {
    const d = e.data || {};
    if (!TIPOS_ETAPA.includes(e.tipo)) erros.push(ref + ': tipo de etapa invalido -> ' + e.tipo);
    if (!TIPOS_DATA.includes(d.tipo)) erros.push(ref + '/' + e.nome + ': tipo de data invalido -> ' + d.tipo);
    if (d.tipo === 'exata' && !re.test(d.valor || '')) {
      erros.push(ref + '/' + e.nome + ': data exata fora do formato AAAA-MM-DD -> ' + d.valor);
    }
    if (d.tipo === 'periodo') {
      if (!re.test(d.valor || '')) erros.push(ref + '/' + e.nome + ': inicio do periodo invalido -> ' + d.valor);
      if (!re.test(d.fim || '')) erros.push(ref + '/' + e.nome + ': fim do periodo invalido -> ' + d.fim);
      if (re.test(d.valor || '') && re.test(d.fim || '') && d.fim < d.valor) {
        erros.push(ref + '/' + e.nome + ': periodo termina antes de comecar');
      }
    }
  });

  if (x.periodo_provas) {
    ['inicio', 'fim'].forEach(k => {
      if (x.periodo_provas[k] && !re.test(x.periodo_provas[k])) {
        erros.push(ref + ': periodo_provas.' + k + ' fora do formato AAAA-MM-DD');
      }
    });
  }
});

if (!window.RADAR_ATUALIZADO) {
  erros.push('window.RADAR_ATUALIZADO nao esta definido');
} else if (!/^\d{2}\/\d{2}\/\d{4}$/.test(window.RADAR_ATUALIZADO)) {
  erros.push('window.RADAR_ATUALIZADO fora do formato DD/MM/AAAA -> ' + window.RADAR_ATUALIZADO);
}

console.log('Concursos: ' + c.length);
console.log('Ultima atualizacao declarada: ' + window.RADAR_ATUALIZADO);
if (avisos.length) {
  console.log('\nAvisos (nao bloqueiam a publicacao): ' + avisos.length);
  avisos.forEach(a => console.log('  - ' + a));
}
if (erros.length) {
  console.error('\nFALHOU com ' + erros.length + ' erro(s). A publicacao foi cancelada:');
  erros.forEach(e => console.error('  - ' + e));
  process.exit(1);
}
console.log('\nVALIDACAO OK. Liberado para publicar.');
