// Gera, a partir do dados.js, as páginas do Radar que o Google consegue ler
// sem executar JavaScript:
//
//   1. uma página estática por concurso, em concurso/<id>/index.html;
//   2. a lista dos concursos escrita direto no index.html (dentro do #root,
//      que o React substitui quando termina de carregar, então o visitante
//      continua vendo o Radar de sempre);
//   3. o sitemap.xml do Radar, com a página principal e todas as páginas
//      de concurso;
//   4. o título e a descrição de busca do index.html, com o ano corrente e
//      o número de concursos com inscrição aberta no dia.
//
// Uso: node gerar-paginas.js <pasta>
// A pasta precisa conter o dados.js e o index.html que serão publicados.
//
// Vida das páginas: cada página existe enquanto o concurso estiver no
// dados.js. Quando o concurso sai do Radar, a página dele deixa de ser gerada
// e a publicação (FTP-Deploy-Action) apaga o arquivo do servidor, porque ele
// sumiu da pasta publicada. O sitemap é refeito do zero a cada publicação.

"use strict";

const fs = require("fs");
const path = require("path");

const BASE = "https://aulanota10.com/radar/";
const UMAMI_ID = "c0d5e94d-5b5d-4cce-b713-8cab72f83ff2";
const MARCA_INICIO = "<!-- LISTA-ESTATICA-INICIO -->";
const MARCA_FIM = "<!-- LISTA-ESTATICA-FIM -->";

const pasta = process.argv[2];
if (!pasta) {
  console.error("Uso: node gerar-paginas.js <pasta com dados.js e index.html>");
  process.exit(1);
}

// ---------- leitura do dados.js ----------

const window = {};
// eslint-disable-next-line no-eval
eval(fs.readFileSync(path.join(pasta, "dados.js"), "utf8"));
const CONCURSOS = (window.CONCURSOS || []).filter((c) => {
  if (!c || !c.id || !/^[a-z0-9-]+$/.test(c.id)) {
    console.warn("Concurso ignorado por id inválido:", c && c.id);
    return false;
  }
  return true;
});

// Data de hoje no fuso de Fortaleza, no formato AAAA-MM-DD.
const HOJE = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/Fortaleza",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}).format(new Date());

// ---------- utilidades ----------

function esc(v) {
  return String(v == null ? "" : v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function ehData(s) {
  return typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s);
}

function dataLonga(s) {
  if (!ehData(s)) return s || "";
  const [a, m, d] = s.split("-");
  return `${d}/${m}/${a}`;
}

function dataCurta(s) {
  if (!ehData(s)) return s || "";
  const [, m, d] = s.split("-");
  return `${d}/${m}`;
}

function textoData(data) {
  if (!data) return "Data a divulgar";
  if (data.tipo === "exata" && ehData(data.valor)) return dataLonga(data.valor);
  if (data.tipo === "periodo" && ehData(data.valor)) {
    return ehData(data.fim) && data.fim !== data.valor
      ? `${dataLonga(data.valor)} a ${dataLonga(data.fim)}`
      : dataLonga(data.valor);
  }
  return data.nota || "Data a divulgar";
}

function inicioData(data) {
  return data && ehData(data.valor) ? data.valor : null;
}

function fimData(data) {
  if (!data) return null;
  if (ehData(data.fim)) return data.fim;
  return ehData(data.valor) ? data.valor : null;
}

function ano(c) {
  const m = String(c.id).match(/(\d{4})$/);
  return m ? m[1] : HOJE.slice(0, 4);
}

function numeroVagas(c) {
  const m = String(c.vagas || "").match(/(\d[\d.]*)\s*vagas?/i);
  return m ? `${m[1]} ${Number(m[1].replace(/\./g, "")) === 1 ? "vaga" : "vagas"}` : "";
}

// Termo de busca: "concurso professor EBTT IFSP" e "concurso professor UFC".
function carreiraTitulo(c) {
  return c.nivel === "EBTT" ? "professor EBTT" : "professor";
}

// Número curto do edital, usado para diferenciar concursos da mesma
// instituição no mesmo ano (por exemplo, dois editais da UFMG).
function editalCurto(c) {
  const m = String(c.numero_edital || "").match(/n[º°o.]*\s*([\d][\d.\/-]*)/i);
  return m ? m[1].replace(/[\/.-]+$/, "").replace(/\/\d{4}$/, "") : "";
}

const REPETIDOS = new Set();

function carreira(c) {
  return c.nivel === "EBTT" ? "professor EBTT" : "professor do Magistério Superior";
}

function cortar(texto, max) {
  const t = String(texto || "").replace(/\s+/g, " ").trim();
  if (t.length <= max) return t;
  const corte = t.slice(0, max - 1);
  return corte.slice(0, corte.lastIndexOf(" ")).replace(/[,.;:]$/, "") + "…";
}

function vazio(v) {
  if (v == null) return true;
  const t = String(v).trim();
  return t === "" || /^consultar o edital\.?$/i.test(t);
}

// ---------- fase do concurso ----------

// Próxima etapa que ainda não terminou, priorizando a prova didática.
function proximaEtapa(c) {
  const futuras = (c.etapas || []).filter((e) => {
    const f = fimData(e.data);
    return f && f >= HOJE;
  });
  futuras.sort((a, b) => inicioData(a.data).localeCompare(inicioData(b.data)));
  return futuras.find((e) => e.tipo === "didatica") || futuras[0] || null;
}

function fase(c) {
  const i = c.inscricao || {};
  const inscricaoCorrendo =
    ehData(i.fim) && i.fim >= HOJE && (!ehData(i.inicio) || i.inicio <= HOJE) &&
    (i.situacao === "aberta" || i.situacao === "abre_em_breve");
  if (inscricaoCorrendo) {
    return { curta: `inscrições até ${dataCurta(i.fim)}`, rotulo: "Inscrições abertas", classe: "aberta" };
  }
  // Prazo geral encerrado, mas algumas áreas ainda recebem inscrição (decisão de 11/10/2026)
  const exc = (i.excecoes || [])
    .filter((x) => x && ehData(x.fim) && x.fim >= HOJE && (!ehData(x.inicio) || x.inicio <= HOJE))
    .sort((a, b) => a.fim.localeCompare(b.fim))[0];
  if (exc) {
    return {
      curta: `inscrições até ${dataCurta(exc.fim)} em parte das áreas`,
      rotulo: "Inscrições abertas em parte das áreas",
      classe: "aberta",
    };
  }
  if (i.situacao === "abre_em_breve" || (ehData(i.inicio) && i.inicio > HOJE)) {
    return {
      curta: ehData(i.inicio) && i.inicio > HOJE ? `inscrições a partir de ${dataCurta(i.inicio)}` : "inscrições em breve",
      rotulo: "Inscrições em breve",
      classe: "breve",
    };
  }
  const e = proximaEtapa(c);
  if (e) {
    const ini = inicioData(e.data);
    const fim = fimData(e.data);
    const nome = e.tipo === "didatica" ? "prova didática" : String(e.nome || "próxima etapa").toLowerCase();
    const curta = ini < HOJE || (ini === HOJE && fim > HOJE)
      ? `${nome} até ${dataCurta(fim)}`
      : `${nome} em ${dataCurta(ini)}`;
    return { curta, rotulo: "Em andamento", classe: "andamento" };
  }
  return { curta: "etapas e datas", rotulo: "Em andamento", classe: "andamento" };
}

// ---------- página de cada concurso ----------

// Rótulos com acento (antes saía "Criterios") e "Tempo de aula" só na didática
// (antes a prova escrita aparecia com "Duração da aula: 4 horas"). 17/11/2026.
const ROTULOS_DETALHE = {
  sorteio: "Sorteio do tema",
  duracao: "Duração",
  arguicao: "Arguição",
  plano_de_aula: "Plano de aula",
  nota_minima: "Nota mínima",
  modalidade: "Modalidade",
  criterios: "Critérios",
  recursos: "Recursos",
  questoes: "Questões",
  materias: "Conteúdo",
  formato: "Formato",
  local: "Local",
  pontuacao: "Pontuação",
  ordem: "Ordem de apresentação",
  convocados: "Convocados",
  peso: "Peso",
};

function rotuloCampo(chave, tipo) {
  if (chave === "duracao" && tipo === "didatica") return "Tempo de aula";
  if (ROTULOS_DETALHE[chave]) return ROTULOS_DETALHE[chave];
  const t = String(chave).replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

// Nome da etapa padronizado; o nome do edital vai ao lado quando diz algo a mais.
const ROTULO_ETAPA = {
  objetiva: "Prova objetiva",
  discursiva: "Prova escrita",
  didatica: "Prova didática",
  pratica: "Prova prática",
  projeto: "Projeto ou plano de trabalho",
  titulos: "Prova de títulos",
  memorial: "Memorial",
  resultado: "Resultado final",
};

function semAcento(t) {
  return String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function rotuloEtapa(e) {
  return ROTULO_ETAPA[e.tipo] || String(e.nome || "Etapa");
}

function nomeNoEdital(e) {
  const a = semAcento(e.nome).replace(/[^a-z]/g, "");
  const b = semAcento(rotuloEtapa(e)).replace(/[^a-z]/g, "");
  return e.nome && a !== b ? e.nome : "";
}

const NIVEL_ROTULO = { graduacao: "Graduação", especializacao: "Especialização", mestrado: "Mestrado", doutorado: "Doutorado" };

function textoValor(v) {
  if (Array.isArray(v)) return v.map(textoValor).join("; ");
  if (v && typeof v === "object") return Object.values(v).map(textoValor).join("; ");
  return String(v == null ? "" : v);
}

function linhaFicha(rotulo, valor) {
  if (vazio(valor)) return "";
  return `<div class="linha"><dt>${esc(rotulo)}</dt><dd>${esc(valor)}</dd></div>`;
}

function blocoEtapas(c) {
  const etapas = c.etapas || [];
  if (!etapas.length) return "";
  const itens = etapas
    .map((e) => {
      const det = e.detalhe || {};
      const detalhes = Object.entries(det)
        .map(([k, v]) => [
          k,
          k === "materias" && Array.isArray(v)
            ? v.map((m) => `${m.nome}: ${m.questoes} ${m.questoes === 1 ? "questão" : "questões"}${m.pontos ? ` (${m.pontos})` : ""}`).join("; ")
            : textoValor(v),
        ])
        .filter(([, v]) => !vazio(v))
        .map(([k, v]) => `<li><strong>${esc(rotuloCampo(k, e.tipo))}:</strong> ${esc(v)}</li>`)
        .join("");
      const temas = e.temas
        ? `<li><strong>Temas:</strong> ${e.temas.min === e.temas.max ? `${e.temas.min} temas publicados` : `de ${e.temas.min} a ${e.temas.max} temas publicados, conforme a área`}; a lista está no edital</li>`
        : "";
      const literal = nomeNoEdital(e);
      const meta = [e.carater, e.peso ? `peso ${e.peso}` : ""].filter((x) => !vazio(x)).join(" · ");
      return `<li class="etapa${e.tipo === "didatica" ? " didatica" : ""}">
  <div class="etapa-data">${esc(!e.data || e.data.tipo === "nao_divulgada" ? "A divulgar" : textoData(e.data))}</div>
  <div class="etapa-corpo">
  <h3 class="etapa-nome">${esc(rotuloEtapa(e))}</h3>
  ${literal ? `<div class="etapa-carater">No edital: ${esc(literal)}</div>` : ""}
  ${meta ? `<div class="etapa-carater">${esc(meta)}</div>` : ""}
  ${e.data && !vazio(e.data.nota) ? `<div class="etapa-carater">${esc(e.data.nota.charAt(0).toUpperCase() + e.data.nota.slice(1))}</div>` : ""}
  ${detalhes || temas ? `<ul class="etapa-detalhes">${detalhes}${temas}</ul>` : ""}
  </div>
</li>`;
    })
    .join("\n");
  return `<section><h2>Etapas e datas</h2><ol class="etapas">${itens}</ol></section>`;
}

function blocoAlteracoes(c) {
  const alts = (c.alteracoes || []).filter((a) => ehData(a.data));
  if (!alts.length) return "";
  return `<section><h2>O que mudou desde o edital</h2><ul class="mudancas">${alts
    .map((a) => `<li><span class="quando">${esc(dataLonga(a.data))}</span><span><strong>Muda:</strong> ${esc(a.muda)}<small>${esc(a.documento)}</small></span></li>`)
    .join("")}</ul></section>`;
}

function blocoVagas(c) {
  const lista = c.areas_formacoes || [];
  if (!lista.length) return "";
  const ins = c.inscritos || {};
  const inscritos = (a) => {
    const cod = a.codigo == null ? "" : String(a.codigo);
    if (!cod) return "";
    if (a.edital && ins[`${a.edital}|${cod}`] != null) return ins[`${a.edital}|${cod}`];
    return ins[cod] != null ? ins[cod] : "";
  };
  const temInscritos = lista.some((a) => inscritos(a) !== "");
  const linhas = lista
    .map((a) => `<tr><td><strong>${esc(a.area)}</strong><small>O edital exige: “${esc(a.requisito || "consulte o edital")}”</small></td><td>${esc([a.edital ? `Edital ${a.edital}` : "", a.campus || ""].filter(Boolean).join(" · "))}</td><td class="num">${esc(a.vagas || "")}</td><td>${esc(NIVEL_ROTULO[a.nivel_minimo] || a.nivel_minimo || "")}</td>${temInscritos ? `<td class="num">${esc(inscritos(a))}</td>` : ""}</tr>`)
    .join("");
  return `<section><h2>Vagas e requisitos</h2><div class="rolagem"><table class="vagas"><thead><tr><th>Área</th><th>Local</th><th class="num">Vagas</th><th>Titulação mínima</th>${temInscritos ? '<th class="num">Inscritos</th>' : ""}</tr></thead><tbody>${linhas}</tbody></table></div><p class="nota">O Radar não decide quem pode concorrer. Confira o requisito no edital oficial antes de se inscrever.</p></section>`;
}

// Preparação Aula Nota 10 (17/11/2026): e-book e curso nas landing pages, mentoria no WhatsApp.
// Perto da prova didática (até 30 dias ou em andamento) a mentoria vem primeiro; longe, o curso.
const LINK_EBOOK = "https://aulanota10.com/ebook/";
const LINK_CURSO = "https://aulanota10.com/";
function linkMentoria(c) {
  const msg = c
    ? `Olá, professor Samuel! Vi o Radar de Concursos e tenho interesse na mentoria para a prova didática do concurso ${c.sigla}${c.edital && c.edital.numero ? ` (edital ${c.edital.numero})` : ""}.`
    : "Olá, professor Samuel! Vi o Radar de Concursos e tenho interesse na mentoria.";
  return `https://wa.me/5584999360222?text=${encodeURIComponent(msg)}`;
}
const ITENS_PREP = {
  ebook: ["E-book gratuito", "5 erros que podem te eliminar na prova de desempenho didático", "Receber o e-book"],
  curso: ["Curso online", "Curso Aula Nota 10: preparação para a prova de desempenho didático", "Conhecer o curso"],
  mentoria: ["Mentoria", "Acompanhamento individual com o professor Samuel", "Falar sobre a mentoria"],
};
function blocoPreparacao(c) {
  const dd = (c.etapas || []).find((e) => e.tipo === "didatica");
  let ordem = ["curso", "ebook", "mentoria"];
  let titulo = "Prepare-se para esta prova didática";
  const ini = dd && inicioData(dd.data);
  const fim = dd && fimData(dd.data);
  if (ini && fim) {
    const dias = Math.round((Date.parse(ini) - Date.parse(HOJE)) / 86400000);
    if (fim >= HOJE && dias <= 30) ordem = ["mentoria", "ebook", "curso"];
    if (fim < HOJE) titulo = "Prepare-se para a sua próxima prova didática";
  }
  const cartoes = ordem
    .map((k, i) => {
      const [rotulo, texto, acao] = ITENS_PREP[k];
      const href = k === "ebook" ? LINK_EBOOK : k === "curso" ? LINK_CURSO : linkMentoria(c);
      return `<a class="prep${i === 0 ? " primeiro" : ""}" href="${esc(href)}"${k === "mentoria" ? ' target="_blank" rel="noopener"' : ""} data-umami-event="preparacao" data-umami-event-lugar="pagina" data-umami-event-item="${k}"><small>${esc(rotulo)}</small><span>${esc(texto)}</span><strong>${esc(acao)} →</strong></a>`;
    })
    .join("");
  return `<section><h2>${esc(titulo)}</h2><div class="preps">${cartoes}</div></section>`;
}

function blocoAvisos(c) {
  const avisos = (c.avisos_edital || []).filter((a) => !vazio(a));
  if (!avisos.length) return "";
  return `<section><h2>Pontos de atenção no edital</h2><ul class="avisos">${avisos
    .map((a) => `<li>${esc(a)}</li>`)
    .join("")}</ul></section>`;
}

function paginaConcurso(c) {
  const f = fase(c);
  const vagas = numeroVagas(c);
  const url = `${BASE}concurso/${c.id}/`;
  const ed = REPETIDOS.has(`${c.sigla}|${ano(c)}`) && editalCurto(c) ? `, edital ${editalCurto(c)}` : "";
  const titulo = `Concurso ${carreiraTitulo(c)} ${c.sigla} ${ano(c)}${ed}: ${vagas ? vagas + ", " : ""}${f.curta}`;
  const descricao = cortar(
    c.observacao ||
      `${c.instituicao} (${c.uf}): ${c.vagas || "vagas"} para ${carreira(c)}. Veja as etapas, as datas e o que o edital exige na prova didática.`,
    158
  );
  const i = c.inscricao || {};
  const periodoInscricao =
    ehData(i.inicio) && ehData(i.fim)
      ? `${dataLonga(i.inicio)} a ${dataLonga(i.fim)}`
      : ehData(i.fim)
      ? `até ${dataLonga(i.fim)}`
      : "";
  const atualizado = (c.fonte_dados && c.fonte_dados.extraido_em) || HOJE;
  const migalhas = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Radar de Concursos Docentes", item: BASE },
      { "@type": "ListItem", position: 2, name: `${c.sigla} ${ano(c)}`, item: url },
    ],
  };

  return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(titulo)} | Radar Aula Nota 10</title>
<meta name="description" content="${esc(descricao)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="${esc(url)}">
<meta property="og:type" content="article">
<meta property="og:locale" content="pt_BR">
<meta property="og:site_name" content="Aula Nota 10">
<meta property="og:title" content="${esc(titulo)}">
<meta property="og:description" content="${esc(descricao)}">
<meta property="og:url" content="${esc(url)}">
<meta property="og:image" content="${BASE}og.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#284696">
<link rel="icon" type="image/png" sizes="32x32" href="/radar/favicon-32.png">
<link rel="apple-touch-icon" sizes="192x192" href="/radar/favicon-192.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Funnel+Display:wght@600;700;800&family=Afacad:wght@400;500;600;700&display=swap" rel="stylesheet">
<script type="application/ld+json">${JSON.stringify(migalhas)}</script>
<style>
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:#F5F1E9;color:#424240}
body{font-family:Afacad,system-ui,sans-serif;font-size:18px;line-height:1.55}
a{color:#284696}
.topo{background:#284696;color:#fff;padding:12px 16px}
.topo-dentro{max-width:900px;margin:0 auto;display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:6px 20px}
.topo a{color:#fff;text-decoration:none;font-family:"Funnel Display",system-ui,sans-serif;font-weight:700;min-height:44px;display:inline-flex;align-items:center}
.topo .marca{font-size:24px;font-weight:800}
.topo .radar{font-size:19px}
main{max-width:900px;margin:0 auto;padding:20px 16px 48px}
.migalhas{font-size:14px;margin-bottom:12px}
h1{font-family:"Funnel Display",system-ui,sans-serif;font-weight:800;color:#284696;font-size:28px;line-height:1.2;margin:4px 0 8px}
h2{font-family:"Funnel Display",system-ui,sans-serif;font-weight:700;color:#284696;font-size:21px;margin:32px 0 10px}
.edital{margin:0 0 14px;font-size:15px}
.selo{display:inline-block;font-weight:600;font-size:14px;padding:3px 12px;border-radius:999px;margin-bottom:10px}
.selo.aberta{background:#CF5645;color:#fff}
.selo.breve{background:#284696;color:#fff}
.selo.andamento{background:#424240;color:#F5F1E9}
.resumo{background:#fff;border-left:4px solid #CF5645;padding:12px 16px;border-radius:6px}
dl{margin:0;background:#fff;border-radius:8px;overflow:hidden}
.linha{display:grid;grid-template-columns:150px 1fr;gap:12px;padding:10px 16px;border-bottom:1px solid #ece6da}
.linha:last-child{border-bottom:0}
dt{font-weight:600}
dd{margin:0}
.etapas,.avisos{padding:0;margin:0;list-style:none}
.etapa{background:#fff;border:1px solid #e2ddd0;border-radius:12px;padding:14px 18px;margin-bottom:10px;display:flex;flex-wrap:wrap;gap:4px 20px}
.etapa.didatica{border:2px solid #CF5645}
.etapa-data{flex:0 0 170px;font-family:"Funnel Display",system-ui,sans-serif;font-weight:700;color:#424240}
.etapa-corpo{flex:999 1 360px;min-width:0}
.etapa-nome{font-weight:700;font-size:19px;margin:0;font-family:Afacad,system-ui,sans-serif;color:#424240}
.etapa.didatica .etapa-nome{color:#a53a2b}
.etapa-carater{font-size:16px;color:#5b5b59}
.etapa-detalhes{margin:8px 0 0;padding-left:18px;font-size:17px}
.mudancas{list-style:none;margin:0;padding:4px 16px;background:#fff;border:1px solid #e2ddd0;border-radius:12px}
.mudancas li{display:flex;flex-wrap:wrap;gap:2px 18px;padding:10px 0;border-top:1px solid #ece6da}
.mudancas li:first-child{border-top:0}
.mudancas .quando{flex:0 0 104px;font-weight:700;color:#284696}
.mudancas small,.vagas small{display:block;font-size:15px;color:#5b5b59;font-weight:400}
.rolagem{overflow-x:auto;background:#fff;border:1px solid #e2ddd0;border-radius:12px}
.vagas{width:100%;min-width:640px;border-collapse:collapse;font-size:17px}
.vagas th{background:#e7ebf6;color:#284696;text-align:left;padding:10px 14px}
.vagas td{padding:10px 14px;border-top:1px solid #ece6da;vertical-align:top}
.vagas .num{text-align:right}
.avisos li{background:#fff;border-radius:8px;padding:10px 16px;margin-bottom:8px;border-left:4px solid #284696}
.botoes{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}
.botao{display:inline-block;padding:12px 18px;border-radius:8px;font-weight:600;text-decoration:none}
.botao.primario{background:#284696;color:#fff}
.botao.secundario{background:#fff;color:#284696;border:2px solid #284696}
.nota{font-size:14px;color:#6b6b68;margin-top:24px}
.botao.laranja{background:#b8432f;color:#fff}
.menu{display:flex;flex-wrap:wrap;gap:2px 14px}
.menu a{font-family:Afacad,system-ui,sans-serif;font-weight:600;font-size:16.5px}
.preps{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
.prep{display:flex;flex-direction:column;gap:4px;text-decoration:none;color:#424240;background:#fff;border:1px solid #e2ddd0;border-radius:12px;padding:14px 16px}
.prep small{font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#5b5b59}
.prep span{flex:1 1 auto;font-size:17px;line-height:1.3}
.prep strong{color:#284696}
.prep.primeiro{background:#284696;border-color:#284696;color:#fff}
.prep.primeiro small{color:#cfd8f0}
.prep.primeiro strong{color:#fff}
@media (max-width:560px){.linha{grid-template-columns:1fr;gap:2px}h1{font-size:24px}.etapa-data{flex:1 1 100%}.botao{flex:1 1 100%;text-align:center}}
</style>
</head>
<body>
<header class="topo"><div class="topo-dentro"><a class="marca" href="https://aulanota10.com">Aula Nota 10</a><nav class="menu" aria-label="Radar e preparação"><a href="/radar/">Radar de Concursos</a><a href="${LINK_EBOOK}" data-umami-event="preparacao" data-umami-event-lugar="pagina-cabecalho" data-umami-event-item="ebook">Material gratuito</a><a href="${LINK_CURSO}" data-umami-event="preparacao" data-umami-event-lugar="pagina-cabecalho" data-umami-event-item="curso">Curso online</a><a href="${linkMentoria(null)}" target="_blank" rel="noopener" data-umami-event="preparacao" data-umami-event-lugar="pagina-cabecalho" data-umami-event-item="mentoria">Mentoria</a></nav></div></header>
<main>
<nav class="migalhas"><a href="/radar/">Radar de Concursos Docentes</a> › ${esc(c.sigla)}</nav>
<span class="selo ${f.classe}">${esc(f.rotulo)}</span>
<h1>Concurso para ${esc(carreira(c))} ${esc(c.sigla)} ${esc(ano(c))}</h1>
<p class="edital">${esc(c.instituicao)} (${esc(c.uf)}). ${esc(c.numero_edital)}</p>
${vazio(c.observacao) ? "" : `<p class="resumo">${esc(c.observacao)}</p>`}
<section><h2>Resumo do concurso</h2><dl>
${linhaFicha("Carreira", c.nivel === "EBTT" ? "EBTT (Ensino Básico, Técnico e Tecnológico)" : "Magistério Superior")}
${linhaFicha("Vagas", c.vagas)}
${linhaFicha("Áreas", c.areas)}
${linhaFicha("Locais", c.campi)}
${linhaFicha("Titulação", c.titulacao)}
${linhaFicha("Regime", c.regime)}
${linhaFicha("Remuneração", c.remuneracao)}
${linhaFicha("Inscrição", periodoInscricao)}
${linhaFicha("Prazo próprio", (i.excecoes || []).map((x) => `${x.areas}, ${ehData(x.inicio) ? dataLonga(x.inicio) + " a " : "até "}${dataLonga(x.fim)}`).join("; "))}
${linhaFicha("Taxa", i.taxa)}
${linhaFicha("Banca", c.banca)}
</dl></section>
${blocoAlteracoes(c)}
${blocoEtapas(c)}
${blocoAvisos(c)}
${blocoVagas(c)}
${blocoPreparacao(c)}
<div class="botoes">
${typeof c.link_oficial !== "string" || vazio(c.link_oficial) ? "" : `<a class="botao primario" href="${esc(c.link_oficial)}" target="_blank" rel="noopener">Ver o edital oficial</a>`}
<a class="botao secundario" href="/radar/?c=${esc(c.id)}">Ver no Radar, com as vagas e os filtros</a>
<a class="botao secundario" href="/radar/">Ver todos os concursos</a>
</div>
<p class="nota">Resumo feito pela Aula Nota 10 a partir do edital e atualizado em ${esc(dataLonga(atualizado))}. As datas podem mudar por retificação; confira sempre o documento oficial.</p>
</main>
<script async defer src="https://cloud.umami.is/script.js" data-website-id="${UMAMI_ID}"></script>
</body>
</html>
`;
}

// ---------- lista estática no index.html ----------

const ORDEM_GRUPOS = [
  ["aberta", "Inscrições abertas"],
  ["breve", "Inscrições em breve"],
  ["andamento", "Concursos em andamento"],
];

function listaEstatica() {
  const grupos = {};
  for (const c of CONCURSOS) {
    const f = fase(c);
    (grupos[f.classe] = grupos[f.classe] || []).push({ c, f });
  }
  const secoes = ORDEM_GRUPOS.filter(([k]) => grupos[k])
    .map(([k, titulo]) => {
      const itens = grupos[k]
        .sort((a, b) => a.c.sigla.localeCompare(b.c.sigla, "pt-BR"))
        .map(({ c, f }) => {
          const vagas = numeroVagas(c);
          return `<li><a href="concurso/${c.id}/">${esc(c.sigla)}: ${esc(c.instituicao)}</a> · ${esc(
            c.nivel
          )}${vagas ? " · " + esc(vagas) : ""} · ${esc(f.curta)}</li>`;
        })
        .join("");
      return `<h2 style="font-size:18px;color:#284696;margin:24px 0 8px">${esc(titulo)}</h2><ul style="padding-left:18px;margin:0">${itens}</ul>`;
    })
    .join("");
  return `${MARCA_INICIO}
<div id="lista-estatica" style="max-width:760px;margin:0 auto;padding:8px 16px 40px;text-align:left;font-family:Afacad,system-ui,sans-serif;color:#424240;line-height:1.6">
<h1 style="font-size:24px;color:#284696;margin:0 0 4px">Radar de Concursos Docentes</h1>
<p style="margin:0">Concursos para professor EBTT e do Magistério Superior com prova de desempenho didático, com as etapas e as datas de cada um.</p>
${secoes}
</div>
${MARCA_FIM}`;
}

function injetarLista(html) {
  const bloco = listaEstatica();
  if (html.includes(MARCA_INICIO) && html.includes(MARCA_FIM)) {
    const ini = html.indexOf(MARCA_INICIO);
    const fim = html.indexOf(MARCA_FIM) + MARCA_FIM.length;
    return html.slice(0, ini) + bloco + html.slice(fim);
  }
  const alvo = /(<div id="carregando">[^<]*<\/div>)/;
  if (!alvo.test(html)) {
    throw new Error('Não achei <div id="carregando"> no index.html para inserir a lista.');
  }
  return html.replace(alvo, `$1\n${bloco}`);
}

// ---------- título e descrição da página principal ----------

// O título e a descrição que o Google mostra na busca são refeitos a cada
// publicação, com o ano corrente e o número de concursos com inscrição
// aberta naquele dia. Os textos de compartilhamento (og:, twitter:) ficam
// como estão no index.html.
function cabecalhoBusca() {
  const abertos = CONCURSOS.filter((c) => fase(c).classe === "aberta").length;
  const titulo = `Concursos para professor ${HOJE.slice(0, 4)}: editais EBTT e universidades | Aula Nota 10`;
  const resto =
    "EBTT e Magistério Superior: vagas, prazos e datas da prova didática, atualizados por quem já foi banca.";
  const descricao =
    abertos === 0
      ? `Concursos para professor ${resto}`
      : `${abertos} ${abertos === 1 ? "concurso" : "concursos"} para professor com inscrições abertas, ${resto}`;
  return { titulo, descricao };
}

function atualizarCabecalho(html) {
  const { titulo, descricao } = cabecalhoBusca();
  const comTitulo = html.replace(/<title>[^<]*<\/title>/, `<title>${esc(titulo)}</title>`);
  const comDescricao = comTitulo.replace(
    /<meta name="description" content="[^"]*">/,
    `<meta name="description" content="${esc(descricao)}">`
  );
  if (comTitulo === html && !html.includes(`<title>${esc(titulo)}</title>`)) {
    throw new Error("Não achei a tag <title> no index.html.");
  }
  if (!/<meta name="description" content="[^"]*">/.test(html)) {
    throw new Error('Não achei <meta name="description"> no index.html.');
  }
  return comDescricao;
}

// ---------- sitemap ----------

function sitemap() {
  const urls = [`  <url><loc>${BASE}</loc><lastmod>${HOJE}</lastmod></url>`].concat(
    CONCURSOS.map((c) => {
      const lm = (c.fonte_dados && c.fonte_dados.extraido_em) || HOJE;
      return `  <url><loc>${BASE}concurso/${c.id}/</loc><lastmod>${ehData(lm) ? lm : HOJE}</lastmod></url>`;
    })
  );
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.join("\n")}
</urlset>
`;
}

// ---------- execução ----------

{
  const vistos = new Set();
  for (const c of CONCURSOS) {
    const k = `${c.sigla}|${ano(c)}`;
    if (vistos.has(k)) REPETIDOS.add(k);
    vistos.add(k);
  }
}

const pastaConcursos = path.join(pasta, "concurso");
fs.rmSync(pastaConcursos, { recursive: true, force: true });
for (const c of CONCURSOS) {
  const dir = path.join(pastaConcursos, c.id);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "index.html"), paginaConcurso(c));
}

const indexPath = path.join(pasta, "index.html");
fs.writeFileSync(indexPath, atualizarCabecalho(injetarLista(fs.readFileSync(indexPath, "utf8"))));
fs.writeFileSync(path.join(pasta, "sitemap.xml"), sitemap());

console.log(`Páginas de concurso geradas: ${CONCURSOS.length}`);
console.log(`Lista estática inserida em ${indexPath}`);
console.log(`Sitemap: ${path.join(pasta, "sitemap.xml")} (${CONCURSOS.length + 1} endereços)`);
