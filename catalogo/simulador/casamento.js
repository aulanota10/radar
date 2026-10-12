/* Porte para JavaScript de catalogo/catalogo.py e catalogo/casamento.py (Radar, Aula Nota 10).
   Mantido função a função igual ao Python; a conferência contra o Python está em
   simulador/conferir.js. Funciona no navegador (window.Casamento) e no Node (module.exports). */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Casamento = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const NAO = 0, DEPENDE = 1, PODE = 2;
  const NOME_NIVEL = { 2: "pode_servir", 1: "depende_da_banca", 0: "nao_serve" };
  const NIVEIS_ACADEMICOS = ["especializacao", "mestrado", "doutorado", "livre_docencia"];
  const NIVEIS_POS = new Set(["especializacao", "residencia", "certificacao", "mestrado", "doutorado", "livre_docencia"]);
  const GRAUS = new Set(["licenciatura", "bacharelado", "tecnologo", null]);
  const MED = new Set(["Medicina I", "Medicina II", "Medicina III"]);

  const PREFIXOS = /^(curso (superior )?de |graduacao (plena )?em |licenciatura (plena )?(em |de )?|bacharelado (em |de )?|bacharel em |licenciado em |tecnologo em |tecnologia em |curso superior de tecnologia em |superior de tecnologia em |habilitacao em )+/;
  const SUFIXOS = / (licenciatura|bacharelado)( plena)?$/;

  function semAcento(s) { return (s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^\x00-\x7F]/g, ""); }
  function normalizar(s) {
    let n = semAcento(s).toLowerCase().replace(/[^a-z0-9 ]/g, " ");
    return n.replace(/\s+/g, " ").trim();
  }
  function chave(s) {
    const n = normalizar(s);
    let k = n.replace(PREFIXOS, "").replace(SUFIXOS, "").trim();
    return k || n;
  }
  const inter = (a, b) => new Set([...a].filter(x => b.has(x)));
  const sub = (a, b) => [...a].every(x => b.has(x));
  const union = (a, b) => new Set([...a, ...b]);

  class Catalogo {
    constructor(dados) {
      this.dados = dados;
      this.formacoes = {}; for (const f of dados.formacoes) this.formacoes[f.nome] = f;
      this.sinonimos = dados.sinonimos; this.sinonimos_pos = dados.sinonimos_pos || {};
      this.areas = {}; for (const a of dados.areas_avaliacao) this.areas[a.nome] = a;
      this._areas_norm = {}; for (const a in this.areas) this._areas_norm[normalizar(a)] = a;
      this.grandes_areas = dados.grandes_areas;
      this._ga_norm = {}; for (const g of this.grandes_areas) this._ga_norm[normalizar(g)] = g;
      this._ga_chaves = new Set(this.grandes_areas.map(chave).concat([
        "ciencias exatas e da terra", "ciencias biologicas", "engenharias", "ciencias da saude",
        "ciencias agrarias", "ciencias sociais aplicadas", "ciencias humanas",
        "linguistica letras e artes", "outra", "multidisciplinar"]));
    }
    nomeCanonico(nome, contexto) {
      if (!nome) return null;
      const k = chave(nome);
      if (contexto === "pos" && k in this.sinonimos_pos) return this.sinonimos_pos[k];
      if (k in this.sinonimos) return this.sinonimos[k];
      if (nome in this.formacoes) return nome;
      return null;
    }
    resolver(nome, contexto) { const c = this.nomeCanonico(nome, contexto); return c ? this.formacoes[c] || null : null; }
    areaAvaliacaoExata(nome) { return this._areas_norm[normalizar(nome)] || null; }
    grandeAreaDe(nome) {
      const ga = this._ga_norm[normalizar(nome)]; if (ga) return ga;
      const f = this.resolver(nome); return f ? f.grande_area : null;
    }
    areasDaFormacao(nome, contexto) {
      const f = this.resolver(nome, contexto);
      if (!f) { const a = this.areaAvaliacaoExata(nome || ""); return a ? [a, []] : [null, []]; }
      return [f.area_avaliacao || null, (f.areas_alternativas || []).slice()];
    }
    eSubareaDe(nome, acima) {
      const hier = this.dados.hierarquia_cnpq || {};
      if (this._ga_norm[normalizar(acima)] || this._ga_chaves.has(chave(acima))) return false;
      const alvos = new Set([chave(acima)]);
      const ca = this.nomeCanonico(acima); if (ca) alvos.add(chave(ca));
      for (const n of new Set([nome, this.nomeCanonico(nome) || nome])) {
        if ((hier[chave(n)] || []).some(x => alvos.has(x))) return true;
      }
      return false;
    }
    comecaCom(nome, inicio, contexto) {
      const ki = chave(inicio);
      if (ki === "ciencias" || ki === "ciencia" || ki === "") return false;
      const c = this.nomeCanonico(nome, contexto);
      const ks = new Set([chave(nome)]); if (c) ks.add(chave(c));
      if (![...ks].some(k => k !== ki && k.startsWith(ki + " "))) return false;
      const fi = this.resolver(inicio, contexto), fn = this.resolver(nome, contexto);
      if (!fn || !fi || !fi.area_avaliacao) return true;
      return fi.area_avaliacao === fn.area_avaliacao;
    }
    restoDoNome(nome, inicio) {
      const k = chave(nome), ki = chave(inicio);
      return k.startsWith(ki + " ") ? k.slice(ki.length).trim() : "";
    }
    areasDoTema(nome, contexto) {
      const partes = [nome || ""].concat((nome || "").split(/[,:;/()]| subarea | subárea /).filter(x => x.trim()));
      for (const parte of partes) { const [p, alt] = this.areasDaFormacao(parte.trim(), contexto); if (p) return new Set([p, ...alt].filter(Boolean)); }
      for (const parte of partes) {
        for (const termo of (this.dados.hierarquia_cnpq || {})[chave(parte)] || []) {
          const [p, alt] = this.areasDaFormacao(termo, contexto); if (p) return new Set([p, ...alt].filter(Boolean));
        }
      }
      return new Set();
    }
    opcoesGraduacao() {
      return Object.values(this.formacoes).filter(f => (f.aparece_como || []).includes("graduacao") && f.tipo !== "grande_area").map(f => f.nome).sort((a, b) => a.localeCompare(b, "pt"));
    }
    opcoesPos() {
      return Object.values(this.formacoes).filter(f => f.tipo !== "grande_area" && f.tipo !== "generico").map(f => f.nome).sort((a, b) => a.localeCompare(b, "pt"));
    }
  }

  function R(nivel, ...motivos) { return { nivel, motivos: motivos.filter(Boolean) }; }
  function melhor(rs) { return rs.length ? rs.reduce((a, b) => (b.nivel > a.nivel ? b : a)) : R(NAO); }
  function junta(...rs) {
    const n = Math.min(...rs.map(r => r.nivel));
    const mot = n > NAO ? rs.flatMap(r => r.motivos) : rs.filter(r => r.nivel === NAO).flatMap(r => r.motivos);
    return R(n, ...mot);
  }

  function validarPerfil(p, cat) {
    const erros = [];
    if (!p.graduacoes || !p.graduacoes.length) erros.push("perfil sem graduação");
    for (const g of p.graduacoes || []) {
      if (!GRAUS.has(g.grau === undefined ? null : g.grau)) erros.push("grau inválido: " + g.grau);
      if (!g.curso) erros.push("graduação sem curso");
    }
    for (const q of p.pos || []) {
      if (!NIVEIS_POS.has(q.nivel)) erros.push("nível de pós inválido: " + q.nivel);
      if (q.area_capes && !cat.areaAvaliacaoExata(q.area_capes)) erros.push("área da CAPES desconhecida: " + q.area_capes);
    }
    return erros;
  }

  function mesmoNome(cat, a, b, contexto) {
    if (!a || !b) return false;
    const ca = cat.nomeCanonico(a, contexto), cb = cat.nomeCanonico(b, contexto);
    if (ca && cb) return ca === cb;
    return chave(a) === chave(b);
  }
  function areasDoCandidato(cat, nome, declarada, contexto) {
    const [p, alt] = cat.areasDaFormacao(nome, contexto);
    const pelo = new Set([p, ...alt].filter(Boolean));
    const dec = declarada ? cat.areaAvaliacaoExata(declarada) : null;
    return [pelo, dec];
  }

  // ------------------------------------------------------------ graduação
  function compararGraduacao(cat, cam, perfil) {
    const grads = perfil.graduacoes || [];
    if (!grads.length) return R(NAO, "sem graduação no perfil");
    if (cam.graduacao_qualquer) return R(PODE, "o caminho aceita qualquer graduação");
    const lista = cam.graduacao || [];
    if (!lista.length) return R(PODE, "o caminho não restringe a graduação");
    const graus = {};
    for (const g of lista) {
      const k = (cat.nomeCanonico(g.nome, "graduacao") || chave(g.nome || "")) + "|" + (g.escala || "");
      (graus[k] = graus[k] || new Set()).add(g.grau === undefined ? null : g.grau);
    }
    const rs = [];
    for (let g of lista) {
      const k = (cat.nomeCanonico(g.nome, "graduacao") || chave(g.nome || "")) + "|" + (g.escala || "");
      const gs = graus[k];
      if (g.nome && (gs.has(null) || (gs.has("licenciatura") && gs.has("bacharelado")))) g = Object.assign({}, g, { grau: null });
      for (const cg of grads) rs.push(umaGraduacao(cat, g, cg, cam.graduacao_afins));
    }
    return melhor(rs);
  }
  function grau_(g, cg) {
    if (!g.grau) return R(PODE);
    if (cg.grau === g.grau) return R(PODE);
    if (!cg.grau) return R(DEPENDE, `o edital exige ${g.grau}; confirme o grau do seu curso`);
    return R(NAO, `o edital exige ${g.grau}`);
  }
  const VAZIAS = new Set(["de", "da", "do", "e", "em", "lingua", "linguas", "literatura", "literaturas", "respectivas", "habilitacao", "com", "a", "o", "as", "os"]);
  function radicais(texto) { return new Set(chave(texto || "").split(" ").filter(w => w && !VAZIAS.has(w)).map(w => w.slice(0, 5))); }
  function concBate(doCandidato, doEdital) {
    const a = new Set(chave(doCandidato).split(" ").filter(Boolean)), b = new Set(chave(doEdital).split(" ").filter(Boolean));
    return a.size > 0 && b.size > 0 && (sub(a, b) || sub(b, a));
  }
  function habilitacao_(g, cg, resto) {
    const h = g.habilitacao;
    if (!h) return R(PODE);
    const dele = cg.habilitacao || resto || "";
    if (dele) return sub(radicais(h), radicais(dele)) ? R(PODE) : R(NAO, `o edital exige habilitação em ${h}`);
    return R(DEPENDE, `o edital exige habilitação em ${h}; confirme a do seu curso`);
  }
  function umaGraduacao(cat, g, cg, afins) {
    const original = cg.curso;
    const curso = cat.nomeCanonico(original, "graduacao") || original;
    const nome = g.nome;
    if (!nome) {
      const r = grau_(g, cg);
      return R(r.nivel, `o edital aceita qualquer ${g.grau || "graduação"}`, ...r.motivos);
    }
    if (mesmoNome(cat, nome, curso, "graduacao") || cat.comecaCom(original, nome, "graduacao")) {
      const resto = cat.restoDoNome(original, nome) || cat.restoDoNome(curso, nome);
      const r = junta(grau_(g, cg), habilitacao_(g, cg, resto));
      return r.nivel ? R(r.nivel, `graduação em ${nome}`, ...r.motivos) : r;
    }
    const esc = g.escala || "curso";
    const [areasC] = areasDoCandidato(cat, curso, null, "graduacao");
    if (esc === "area_capes") {
      const alvo = cat.areaAvaliacaoExata(nome) || cat.areasDaFormacao(nome, "graduacao")[0];
      if (alvo && areasC.has(alvo)) {
        const r = grau_(g, cg);
        const fc = cat.resolver(curso, "graduacao") || {};
        const firme = fc.area_avaliacao === alvo && fc.confianca === "alta" && cat.areaAvaliacaoExata(nome) && !afins;
        return R(Math.min(firme ? PODE : DEPENDE, r.nivel), `o edital pede graduação na área ${nome}, e ${curso} está em ${alvo}`, ...r.motivos);
      }
    }
    if (esc === "grande_area_capes") {
      const ga = cat.grandeAreaDe(nome);
      const fc = cat.resolver(curso, "graduacao");
      if (ga && fc && fc.grande_area === ga) {
        const r = grau_(g, cg);
        const teto = fc.confianca === "alta" && !afins ? PODE : DEPENDE;
        const extra = afins ? "; o edital fala em áreas afins" : "";
        return R(Math.min(teto, r.nivel), `o edital pede graduação na grande área ${nome}, e ${curso} está nela${extra}`, ...r.motivos);
      }
    }
    if (afins) {
      const [pv, alt] = cat.areasDaFormacao(nome, "graduacao");
      if (inter(areasC, new Set([pv, ...alt].filter(Boolean))).size) {
        const r = grau_(g, cg);
        return R(Math.min(DEPENDE, r.nivel), `o edital aceita graduação afim a ${nome}`, ...r.motivos);
      }
    }
    return R(NAO);
  }

  // ------------------------------------------------------------ pós
  const rank = n => NIVEIS_ACADEMICOS.indexOf(n);
  function compararNivel(niveis, p, medica) {
    const n = p.nivel;
    if (niveis.includes(n)) return R(PODE);
    if (n === "residencia" && niveis.includes("especializacao")) return R(PODE, "residência conta como especialização");
    if (niveis.includes("residencia") || niveis.includes("certificacao")) return R(NAO);
    if (niveis.length === 1 && niveis[0] === "livre_docencia") return R(NAO);
    const acad = niveis.filter(x => NIVEIS_ACADEMICOS.includes(x));
    if (acad.length && NIVEIS_ACADEMICOS.includes(n) && rank(n) > Math.max(...acad.map(rank))) {
      const teto = acad.reduce((a, b) => (rank(b) > rank(a) ? b : a));
      if (teto === "especializacao" && medica) return R(DEPENDE, `o edital pede título de especialista; confirme se aceita ${n} no lugar`);
      return R(PODE, `${n} atende a exigência de ${teto} na mesma área`);
    }
    return R(NAO);
  }
  function areaExata(cat, nome, dec, areasC, prog) {
    const exata = cat.areaAvaliacaoExata(nome);
    if (!exata) return null;
    if (dec === exata) return R(PODE, `programa na área de avaliação ${exata}, como você declarou`);
    if (!dec && cat.areasDaFormacao(prog, "pos")[0] === exata) return R(DEPENDE, `o edital pede a área ${exata}; pelo catálogo, ${prog} está nela; confirme a área do seu programa`);
    return null;
  }
  function medicina(areas) { const s = new Set(areas); return [...s].some(x => MED.has(x)) ? union(s, MED) : s; }
  function medica(cat, e) { return (e.areas || []).some(a => { const f = cat.resolver(a.nome, "pos"); return f && f.tipo === "especialidade_medica"; }); }
  const escRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  function compararArea(cat, e, p) {
    const areas = e.areas || [];
    const niveis = e.niveis || [];
    const academico = !niveis.some(x => x === "residencia" || x === "certificacao") && ["especializacao", "mestrado", "doutorado", "livre_docencia"].includes(p.nivel);
    const prog = p.programa;
    if (!areas.length) return R(PODE, (niveis.length ? niveis : ["pós"]).join(" ou ") + " em qualquer área");
    let [areasC, dec] = areasDoCandidato(cat, prog, p.area_capes, "pos");
    if (dec) { const principal = cat.areasDaFormacao(prog, "pos")[0]; areasC = principal === dec ? union(areasC, new Set([dec])) : new Set([dec]); }
    const rs = [];
    for (const a of areas) {
      const nome = a.nome;
      if (!nome) continue;
      if (mesmoNome(cat, nome, prog, "pos")) {
        const conc = a.concentracao;
        if (!conc || chave(conc) === chave(nome) || chave(conc) === chave(prog || "")) rs.push(R(PODE, `pós em ${nome}`));
        else if (p.concentracao) rs.push(chave(p.concentracao) === chave(conc) ? R(PODE, `pós em ${nome}, concentração ${conc}`) : R(NAO, `o edital exige concentração em ${conc}`));
        else rs.push(R(DEPENDE, `o edital exige ${nome} com concentração em ${conc}; confirme a do seu programa`));
        continue;
      }
      let esc = a.escala || "curso";
      const antes = rs.length;
      const fn = cat.resolver(nome, "pos") || {};
      const especialidade = fn.tipo === "especialidade_medica" && niveis.some(x => x === "especializacao" || x === "residencia");
      const aproximar = academico && !especialidade;
      if (aproximar && !a.concentracao && cat.comecaCom(prog, nome, "pos") &&
          !(!fn.area_avaliacao && dec && cat.grandeAreaDe(nome) && cat.areas[dec].grande_area !== cat.grandeAreaDe(nome))) {
        rs.push(R(PODE, `o edital pede ${nome}, e seu programa (${prog}) é um recorte dessa área`));
        continue;
      }
      if (esc === "curso" || esc === "area_capes") {
        let r = areaExata(cat, nome, dec, areasC, prog);
        const conc = a.concentracao;
        if (r && conc && !(p.concentracao && concBate(p.concentracao, conc))) {
          if (concBate(prog || "", conc)) { /* a concentração pedida é o próprio nome do programa */ }
          else r = p.concentracao ? null : R(DEPENDE, ...r.motivos, `o edital exige concentração em ${conc}; confirme a do seu programa`);
        }
        if (r) rs.push(r);
      }
      if ((esc === "curso" || esc === "area_capes") && rs.length === antes && !cat.areaAvaliacaoExata(nome) && (cat.resolver(nome, "pos") || {}).tipo === "grande_area") esc = "grande_area_capes";
      if (esc === "grande_area_capes") {
        const ga = cat.grandeAreaDe(nome);
        if (ga && dec && cat.areas[dec].grande_area === ga) rs.push(R(PODE, `programa na grande área ${nome}, pela área que você declarou`));
        else {
          const fp = cat.resolver(prog, "pos");
          if (ga && fp && fp.grande_area === ga) rs.push(R(fp.confianca === "alta" ? PODE : DEPENDE, `o edital pede a grande área ${nome}, e ${prog} está nela`));
        }
      }
      if (aproximar && rs.length === antes && cat.comecaCom(prog, nome, "pos")) {
        const generico = !fn.area_avaliacao;
        const gaNome = cat.grandeAreaDe(nome);
        const fora = generico && dec && gaNome && cat.areas[dec].grande_area !== gaNome;
        if (fora) rs.push(R(DEPENDE, `o edital pede ${nome}, e seu programa (${prog}) tem esse nome, mas você o declarou na área ${dec}, fora de ${gaNome}`));
        else rs.push(R(PODE, `o edital pede ${nome}, e seu programa (${prog}) é ${generico ? "uma delas" : "um recorte dessa área"}`));
      }
      if (aproximar && rs.length === antes && dec && niveis.some(x => x === "mestrado" || x === "doutorado")) {
        const cobre = (cat.dados.guarda_chuva || {})[chave(nome)] || [];
        const concOk = !a.concentracao || (p.concentracao && concBate(p.concentracao, a.concentracao));
        if (cobre.includes(dec) && concOk) {
          if (chave(nome) === "medicina") rs.push(R(PODE, `o edital pede Medicina, e seu programa está na área ${dec}, como você declarou`));
          else rs.push(R(DEPENDE, `o edital pede ${nome}; seu programa (${prog}) está na área de avaliação ${dec}, que esse nome cobre; confira se a banca aceita`));
        }
      }
      if (aproximar && rs.length === antes && cat.eSubareaDe(prog, nome)) rs.push(R(DEPENDE, `pela tabela do CNPq, ${prog} é subárea de ${nome}`));
      if (aproximar && rs.length === antes && cat.eSubareaDe(nome, prog) && !(p.concentracao && !concBate(p.concentracao, nome)))
        rs.push(R(DEPENDE, `o edital pede ${nome}, que na tabela do CNPq fica dentro de ${prog}; confira se sua tese é nesse tema`));
      if (aproximar && rs.length === antes && a.area_do_concurso && prog && new RegExp("(^| )" + escRe(chave(prog)) + "( |$)").test(chave(nome)))
        rs.push(R(PODE, `a área do concurso (${nome}) é da sua área (${prog})`));
      if (rs.length === antes && (e.afins || (aproximar && a.area_do_concurso))) {
        const alvo = cat.areasDoTema(nome, "pos");
        const fp = cat.resolver(prog, "pos") || {};
        if (fp.tipo === "especialidade_medica" && !MED.has(fn.area_avaliacao)) continue;
        const outraConc = !e.afins && a.area_do_concurso && p.concentracao && !inter(radicais(p.concentracao), radicais(nome)).size;
        if (inter(medicina(areasC), medicina(alvo)).size && !outraConc) {
          if (e.afins) rs.push(R(DEPENDE, `o edital aceita áreas afins a ${nome}`));
          else rs.push(R(DEPENDE, `o edital pede a área do concurso (${nome}); confira se seu programa ou sua tese é nela`));
        }
      }
    }
    return melhor(rs);
  }

  const SOBRA_IGNORA = new Set(["edita", "exige", "douto", "mestr", "tese", "defen", "disse", "area", "sem", "nomea", "progr", "que", "na", "no"]);
  function compararExigencia(cat, e, p, areaVaga) {
    const rn = compararNivel(e.niveis || [], p, medica(cat, e));
    if (rn.nivel === NAO) return R(NAO);
    const ra = compararArea(cat, e, p);
    let r = junta(rn, ra);
    if (r.nivel > NAO && e.tese_na_area && !e.nota && areaVaga) {
      const tema = chave(areaVaga), prog = chave(p.programa || "");
      if (r.nivel === PODE && prog && !(tema === prog || tema.startsWith(prog + " ") || prog.startsWith(tema + " ")))
        r = R(DEPENDE, ...r.motivos, `o edital exige tese na área do concurso (${areaVaga}); confira o tema da sua`);
    }
    if (r.nivel === PODE && !e.tese_na_area && (e.nota || "").includes("nfase")) r = R(DEPENDE, ...r.motivos, "o edital pede ênfase num tema: " + e.nota);
    if (r.nivel > NAO && e.tese_na_area && e.nota) {
      if (!(e.areas || []).length && areaVaga) {
        const alvo = cat.areasDoTema(areaVaga, "pos");
        const [areasC, dec] = areasDoCandidato(cat, p.programa, p.area_capes, "pos");
        const tema = chave(areaVaga), prog = chave(p.programa || "");
        const ligado = !!prog && (tema === prog || tema.startsWith(prog + " "));
        const todas = dec ? union(areasC, new Set([dec])) : areasC;
        if (alvo.size && !ligado && !inter(todas, alvo).size) return R(NAO, "o edital exige tese num tema fora da área do seu programa");
      }
      const nomes = radicais((e.areas || []).map(a => a.nome || "").join(" "));
      const sobra = [...radicais(e.nota)].filter(x => !nomes.has(x) && !SOBRA_IGNORA.has(x));
      if (r.nivel === PODE && sobra.length) r = R(DEPENDE, ...r.motivos, "o edital exige tese ou dissertação num tema específico: " + e.nota);
    }
    if (r.nivel > NAO && p.concluida === false) r = R(DEPENDE, ...r.motivos, `seu ${p.nivel} está em curso; confira em que momento o edital exige o título (inscrição ou posse)`);
    return r;
  }
  function compararPos(cat, cam, perfil, areaVaga) {
    const exig = cam.exigencias || [];
    if (!exig.length) return R(PODE);
    const pos = perfil.pos || [];
    if (!pos.length) return R(NAO, "o caminho exige pós e o perfil não tem");
    const melhores = exig.map(e => melhor(pos.map(q => compararExigencia(cat, e, q, areaVaga))));
    exig.forEach((e, i) => {
      const m = melhores[i];
      if (m.nivel === NAO && (e.niveis || []).length === 1 && e.niveis[0] === "certificacao") {
        const nomes = (e.areas || []).map(a => a.nome || "").join(", ") || "a formação pedida";
        m.nivel = DEPENDE;
        m.motivos = [`o edital exige também certificação ou formação em ${nomes}, que o perfil não registra; confira se você tem`];
      }
    });
    return junta(...melhores);
  }

  function avaliarVaga(cat, vaga, perfil) {
    const ri = vaga.requisito_interpretado;
    if (!ri) return [R(NAO, "vaga sem requisito interpretado"), null];
    let best = R(NAO), idx = null;
    (ri.caminhos || []).forEach((cam, i) => {
      const r = junta(compararGraduacao(cat, cam, perfil), compararPos(cat, cam, perfil, vaga.area_conhecimento));
      if (r.nivel > best.nivel) { best = r; idx = i; }
    });
    if (best.nivel > NAO) {
      const cam = ri.caminhos[idx];
      if ((cam.outras_exigencias || []).length) best.motivos.push("confira também: " + cam.outras_exigencias.join("; "));
      if (ri.ambiguo && best.nivel === PODE) best = R(DEPENDE, ...best.motivos, "o requisito do edital admite duas leituras: " + (ri.nota || ""));
    }
    return [best, idx];
  }

  return { NAO, DEPENDE, PODE, NOME_NIVEL, Catalogo, normalizar, chave, validarPerfil, avaliarVaga };
});
