"""Alerta de concurso novo (ferramenta 2), ENSAIO: não envia nada.

Liga o casamento do catálogo (catalogo/casamento.py) à cadeia. Um concurso é novo no
dia em que a primeira extração dele aparece no aulanota10/vigia-documentos, isto é,
quando o slug está nas extrações e não está no estado da rodada anterior dos alertas
(alertas/estado/estado.json, campo concursos). Para cada concurso novo e cada perfil do
grupo, o casamento diz se cada vaga pode servir, depende da banca ou não serve.

Vai para a fila só o "pode servir" de concurso ativo, com área não cancelada e inscrição
que não terminou (fim desconhecido também vai, com "confira o prazo no edital"). Uma
mensagem por perfil e por concurso, juntando as vagas. O "depende da banca" e as vagas
sem requisito interpretado vão só para o relatório. A mensagem sai já nos parâmetros do
modelo alerta_concurso_novo (alertas/modelos.py) e é conferida contra os limites da Meta.

Este script tem de rodar ANTES de agenda.py na rodada diária, porque agenda.py regrava
o estado. Sem estado anterior, a execução é linha de base e não gera fila.

Uso:
  python3 alertas/concurso_novo.py --vigia ../vigia-documentos --perfis perfis.json \
      --anterior alertas/estado/estado.json --hoje AAAA-MM-DD --saida /tmp/saida \
      [--novos slug1,slug2]   (só para ensaio: trata esses slugs como novos)
"""
import argparse, collections, datetime as dt, json, os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "..", "catalogo"))

import agenda  # noqa: E402
import modelos  # noqa: E402
from catalogo import Catalogo  # noqa: E402
import casamento  # noqa: E402


def novos_concursos(concursos, anterior, forcados=None):
    if forcados:
        return sorted(s for s in forcados if s in concursos), False
    if not anterior or not os.path.exists(anterior):
        return [], True
    conhecidos = set(json.load(open(anterior, encoding="utf-8")).get("concursos", {}))
    return sorted(s for s in concursos if s not in conhecidos), False


def rotulo_vaga(r):
    area = (r.get("area") or "").strip()
    return f"{area}, vaga {r['vaga']}" if area and r.get("vaga") else (area or f"vaga {r['vaga']}")


def executar(vigia, perfis, anterior, hoje, forcados=None):
    cat = Catalogo.carregar()
    concursos = agenda.ler_concursos(vigia)
    novos, base = novos_concursos(concursos, anterior, forcados)
    rel = collections.defaultdict(list)
    fila = []  # (perfil_id, slug, params, vagas)
    if base:
        return fila, rel, novos, base
    sub = {s: concursos[s] for s in novos}
    for s in novos:
        c = concursos[s]
        sem_req = [casamento.codigo_vaga(v) for v in c.get("vagas") or [] if not v.get("requisito_interpretado")]
        if sem_req:
            rel["sem_requisito"].append(f"{agenda.nome_concurso(c)}: {len(sem_req)} vaga(s) sem requisito interpretado ({', '.join(sem_req[:8])}); não entram no casamento.")
    for p in perfis:
        erros = casamento.validar_perfil(p, cat)
        if erros:
            rel["perfil_invalido"].append(f"{p.get('id')}: {'; '.join(erros)}")
            continue
        res = casamento.casar(cat, sub, p, hoje)
        por_conc = collections.defaultdict(list)
        for r in res:
            if r["excluida"] or r["inscricao_aberta"] is False:
                continue
            if r["nivel"] == "pode_servir":
                por_conc[r["concurso"]].append(r)
            elif r["nivel"] == "depende_da_banca":
                rel["depende"].append(f"{p['id']} · {r['nome_concurso']} · {rotulo_vaga(r)}: {'; '.join(r['motivos'])[:300]}")
        for slug, rs in sorted(por_conc.items()):
            fins = sorted({str(r["inscricao_fim"])[:10] for r in rs if r["inscricao_fim"]})
            reqs = list(dict.fromkeys(modelos.limpa(r["requisito_literal"]) for r in rs if r["requisito_literal"]))
            req = reqs[0] if reqs else None
            if len(reqs) > 1:
                req = f"varia por vaga; o de {rotulo_vaga(rs[0])} é: {req}"
            params = modelos.params_concurso_novo(
                rs[0]["nome_concurso"], [rotulo_vaga(r) for r in rs],
                fins[0] if fins else None, req, rs[0]["link"], prazo_varia=len(fins) > 1)
            if len(fins) > 1:
                rel["prazo_variado"].append(f"{p['id']} · {rs[0]['nome_concurso']}: prazos diferentes entre as vagas ({', '.join(fins)}); a mensagem leva o mais cedo e avisa que varia.")
            pr = modelos.problemas(modelos.CONCURSO_NOVO, params)
            if pr:
                rel["fora_do_limite"].append(f"{p['id']} · {rs[0]['nome_concurso']}: {'; '.join(pr)}")
                continue
            fila.append((p["id"], slug, params, rs))
    return fila, rel, novos, base


def montar_fila(fila, hoje, novos, base):
    l = [f"# Alerta de concurso novo · {agenda.fmt(hoje)} · ENSAIO, não enviar", ""]
    if base:
        return "\n".join(l + ["Linha de base: sem estado anterior, nenhum concurso é tratado como novo.", ""])
    l += [f"{len(fila)} mensagem(ns) para {len({f[0] for f in fila})} perfil(is), sobre {len(novos)} concurso(s) novo(s).", ""]
    for pid, slug, params, rs in fila:
        l += [f"**Para: {pid} · {params[0]}** (modelo {modelos.CONCURSO_NOVO['nome']})", "", "```",
              modelos.render(modelos.CONCURSO_NOVO, params), "", modelos.RODAPE, "```", ""]
    return "\n".join(l)


def montar_relatorio(rel, fila, novos, base, n_perfis, hoje):
    titulos = [("sem_requisito", "Vagas de concurso novo sem requisito interpretado"),
               ("depende", "Depende da banca (fora da fila; candidato ao resumo semanal)"),
               ("prazo_variado", "Concurso com prazo de inscrição diferente entre as vagas do mesmo perfil"),
               ("fora_do_limite", "Mensagens fora dos limites do modelo (não entraram na fila)"),
               ("perfil_invalido", "Perfis inválidos")]
    l = [f"# Relatório do alerta de concurso novo · {agenda.fmt(hoje)}", ""]
    if base:
        l.append("Linha de base. Nada a avisar.")
        return "\n".join(l)
    l += [f"Concursos novos: {len(novos)}{' (' + ', '.join(novos) + ')' if novos else ''}. Perfis: {n_perfis}. Mensagens na fila: {len(fila)}.", ""]
    for k, t in titulos:
        if rel.get(k):
            l += [f"## {t} ({len(rel[k])})", ""] + [f"- {x}" for x in rel[k][:60]]
            if len(rel[k]) > 60:
                l.append(f"- e mais {len(rel[k]) - 60}.")
            l.append("")
    return "\n".join(l)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vigia", required=True)
    ap.add_argument("--perfis", required=True, help="JSON com a lista de perfis do grupo")
    ap.add_argument("--anterior", help="estado.json da rodada anterior dos alertas")
    ap.add_argument("--hoje", default=dt.date.today().isoformat())
    ap.add_argument("--saida", required=True)
    ap.add_argument("--novos", help="ensaio: slugs separados por vírgula tratados como novos")
    a = ap.parse_args()
    hoje = dt.date.fromisoformat(a.hoje)
    perfis = json.load(open(a.perfis, encoding="utf-8"))
    forc = [s.strip() for s in a.novos.split(",")] if a.novos else None
    fila, rel, novos, base = executar(a.vigia, perfis, a.anterior, hoje, forc)
    os.makedirs(a.saida, exist_ok=True)
    open(os.path.join(a.saida, f"concurso-novo-{a.hoje}.md"), "w", encoding="utf-8").write(montar_fila(fila, hoje, novos, base))
    open(os.path.join(a.saida, f"concurso-novo-relatorio-{a.hoje}.md"), "w", encoding="utf-8").write(
        montar_relatorio(rel, fila, novos, base, len(perfis), hoje))
    print(f"concursos novos: {len(novos)}; mensagens: {len(fila)}")


if __name__ == "__main__":
    main()
