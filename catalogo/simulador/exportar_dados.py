"""Gera simulador/dados/vagas.json e simulador/dados/catalogo.json a partir das extrações
do vigia-documentos e de catalogo/formacoes.json, para o simulador do alerta.
Uso: python3 catalogo/simulador/exportar_dados.py --vigia ../vigia-documentos [--hoje AAAA-MM-DD]"""
import argparse, datetime as dt, json, os, subprocess, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import casamento as C  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--vigia", required=True); ap.add_argument("--hoje", default=dt.date.today().isoformat())
a = ap.parse_args()
cat = C.Catalogo.carregar()
conc = C.agenda.ler_concursos(a.vigia)
hoje = dt.date.fromisoformat(a.hoje)
vagas, concursos = [], {}
for slug, c in sorted(conc.items()):
    sit, canceladas = C.agenda.situacao(c)
    concursos[slug] = {"nome": C.agenda.nome_concurso(c), "instituicao": C.agenda.val(c.get("instituicao")),
                       "carreira": C.agenda.val(c.get("carreira")), "cidade_uf": C.agenda.val(c.get("cidade_uf")),
                       "link": C.agenda.link(c), "situacao": sit}
    for v in c.get("vagas") or []:
        cod = C.codigo_vaga(v)
        excl = None
        if sit != "ativo": excl = f"concurso {sit}"
        elif cod in canceladas: excl = "área cancelada"
        elif v.get("vagas_imediatas") == 0 and not v.get("limite_aprovados"): excl = "vaga suprimida (zero vagas)"
        fim = C.fim_inscricao(c, cod)
        ri = v.get("requisito_interpretado") or {}
        vagas.append({"concurso": slug, "vaga": cod, "area_conhecimento": v.get("area_conhecimento"),
                      "requisito_literal": v.get("requisito_literal"), "titulacao_minima": v.get("titulacao_minima"),
                      "vagas_imediatas": v.get("vagas_imediatas"), "excluida": excl, "inscricao_fim": str(fim)[:10] if fim else None,
                      "requisito_interpretado": {"caminhos": ri.get("caminhos"), "ambiguo": ri.get("ambiguo"), "nota": ri.get("nota")}})
os.makedirs(os.path.join(AQUI, "dados"), exist_ok=True)
sha = subprocess.run(["git", "-C", a.vigia, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
json.dump({"gerado_em": a.hoje, "vigia_commit": sha, "concursos": concursos, "vagas": vagas},
          open(os.path.join(AQUI, "dados", "vagas.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
d = cat.dados
json.dump({k: d[k] for k in ("versao", "grandes_areas", "areas_avaliacao", "formacoes", "sinonimos", "sinonimos_pos", "guarda_chuva", "hierarquia_cnpq")},
          open(os.path.join(AQUI, "dados", "catalogo.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(len(vagas), "vagas,", len(concursos), "concursos")
