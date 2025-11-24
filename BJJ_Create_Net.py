import csv
import re
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from snakes.nets import *

#PARSER DE ESTADOS -------------------------------------------------------------
#extrae solo la posición donde se encuentra Pos(...), ignora ModP
def parse_posicion(estado_str, actor):
    if not estado_str:
        return None
    match = re.search(r'Pos\((.*?)\)', estado_str)
    if not match:
        return None
    contenido = match.group(1)
    for actor_estado in contenido.split(','):
        a, valor = actor_estado.strip().split(':')
        if a.strip() == actor:
            return valor.strip()
    return None

#lee el csv y devuelve una lista de [ID, tecnica, iniA, iniO, exA, exO, faA, faO
def leer_tecnicas(csv_file):
    lista = []
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            fila = [
                row['ID'],
                row['Nombre de la Técnica'],
                parse_posicion(row['Estado Inicial (Notación)'], 'A'),
                parse_posicion(row['Estado Inicial (Notación)'], 'O'),
                parse_posicion(row['Estado Final Exitoso (Notación)'], 'A'),
                parse_posicion(row['Estado Final Exitoso (Notación)'], 'O'),
                parse_posicion(row['Estado Final Fallido (Notación)'], 'A'),
                parse_posicion(row['Estado Final Fallido (Notación)'], 'O')
            ]
            lista.append(fila)
    return lista


# --- SIMETRÍA A/O -------------------------------------------------------------
#expandir simetria hace que se generen las transiciones tomando a O como actor principal para que pueda realizar las mismas técnicas que A
def expandir_simetria(tecnicas):
    nuevas = []
    for (id_, nombre, iniA, iniO, exA, exO, faA, faO) in tecnicas:
        base = f"{id_}_{nombre.replace(' ', '_')}"
        # Versión A actúa (original)
        nuevas.append((f"{base}_A", nombre + "_A", iniA, iniO, exA, exO, faA, faO))
        # Versión O actúa (invertida)
        if iniA or iniO:
            nuevas.append((f"{base}_O", nombre + "_O", iniO, iniA, exO, exA, faO, faA))
    return nuevas


# --- GENERADOR DEL MODELO -------------------------------------------------------------
"""
-crea el modelo de petri coloreado simetrico, con técnicas efectuadas por ambos actores
-también evita la duplicación de los arcos generando una función add_arc_safely() que permite "unir" transiciones duplicadas y consumir mas tokens
-se genera el modelo en un archivo aparte con el modelo llamasdo BJJ_CPN-py utilizando snakes
"""

def generar_modelo_petri(tecnicas, output_file="BJJ_CPN.py"):
    import textwrap
    # --- Simetría: duplicar técnicas para ambos luchadores -----------------
    tecnicas_sim = []
    for t in tecnicas:
        id_, nombre, iniA, iniO, exA, exO, faA, faO = t
        # Original (A ataca)
        tecnicas_sim.append((id_, nombre, iniA, iniO, exA, exO, faA, faO))
        # Versión invertida (O ataca)
        tecnicas_sim.append((
            f"{id_}_inv", f"{nombre}",
            iniO, iniA, exO, exA, faO, faA
        ))

    # --- Recolectar lugares únicos ----------------------------------------
    places = set()
    for _, _, iniA, iniO, exA, exO, faA, faO in tecnicas_sim:
        for p in [iniA, iniO, exA, exO, faA, faO]:
            if p:
                places.add(p)

    # --- Escritura del archivo --------------------------------------------
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# -*- coding: utf-8 -*-\n")
        f.write("#BJJ_CPN - Modelo de Red de Petri Coloreada (CPN) para técnicas de Brazilian Jiu-Jitsu\n")

        # DEPENDENCIAS Y FUNCIÓN AUXILIAR
        f.write(textwrap.dedent("""
        from snakes.nets import *
        from snakes.plugins import load
        load(['gv'], 'snakes.nets', 'nets')

        def add_arc_safely(net, place, transition, label, direction):
            \"\"\"Añade arcos evitando duplicados o conflictos de restricción.\"\"\"
            try:
                if direction == "in":
                    net.add_input(place, transition, label)
                elif direction == "out":
                    net.add_output(place, transition, label)
            except ConstraintError:
                pass  # Ignorar duplicados
        """))

        # CREACIÓN DE LA RED
        f.write("\n\nnet = PetriNet('BJJ_CPN')\n")
        f.write("Luchador = ['A', 'O']\n\n")

        # PLACES
        f.write("# PLACES --------------------------------------------------------------------\n")
        for p in sorted(places):
            f.write(f'net.add_place(Place("{p}"))\n')
        f.write("\n")

        # TRANSICIONES SIMÉTRICAS
        f.write("# TRANSITIONS (Simétricas A/O) ----------------------------------------------\n")
        for (id_, nombre, iniA, iniO, exA, exO, faA, faO) in tecnicas_sim:
            t_name = f"{id_}_{nombre.replace(' ', '_')}"
            t_exitoso = f"{t_name}_exitoso"
            t_fallido = f"{t_name}_fallido"

            # --- Exitosa ---
            f.write(f'net.add_transition(Transition("{t_exitoso}"))\n')
            if iniA and iniO and iniA == iniO:
                f.write(f'add_arc_safely(net, "{iniA}", "{t_exitoso}", MultiArc([Value("A"), Value("O")]), "in")\n')
            else:
                if iniA:
                    f.write(f'add_arc_safely(net, "{iniA}", "{t_exitoso}", Value("A"), "in")\n')
                if iniO:
                    f.write(f'add_arc_safely(net, "{iniO}", "{t_exitoso}", Value("O"), "in")\n')

            if exA and exO and exA == exO:
                f.write(f'add_arc_safely(net, "{exA}", "{t_exitoso}", MultiArc([Value("A"), Value("O")]), "out")\n')
            else:
                if exA:
                    f.write(f'add_arc_safely(net, "{exA}", "{t_exitoso}", Value("A"), "out")\n')
                if exO:
                    f.write(f'add_arc_safely(net, "{exO}", "{t_exitoso}", Value("O"), "out")\n')

            f.write("\n")

            # --- Fallida ---
            f.write(f'net.add_transition(Transition("{t_fallido}"))\n')
            if iniA and iniO and iniA == iniO:
                f.write(f'add_arc_safely(net, "{iniA}", "{t_fallido}", MultiArc([Value("A"), Value("O")]), "in")\n')
            else:
                if iniA:
                    f.write(f'add_arc_safely(net, "{iniA}", "{t_fallido}", Value("A"), "in")\n')
                if iniO:
                    f.write(f'add_arc_safely(net, "{iniO}", "{t_fallido}", Value("O"), "in")\n')

            if faA and faO and faA == faO:
                f.write(f'add_arc_safely(net, "{faA}", "{t_fallido}", MultiArc([Value("A"), Value("O")]), "out")\n')
            else:
                if faA:
                    f.write(f'add_arc_safely(net, "{faA}", "{t_fallido}", Value("A"), "out")\n')
                if faO:
                    f.write(f'add_arc_safely(net, "{faO}", "{t_fallido}", Value("O"), "out")\n')

            f.write("\n")

        # MARCADO INICIAL
        f.write("# MARCADO INICIAL -----------------------------------------------------------\n")
        f.write('net.place("De_Pie").add("A")\n')
        f.write('net.place("De_Pie").add("O")\n\n')

        f.write('print("Modelo BJJ_CPN simétrico cargado correctamente.")\n')

    print(f"Modelo CPN guardado en: {output_file}")


# --- VISUALIZACIÓN -------------------------------------------------------------

def visualizar_red(tecnicas, output_pdf="Model_visualization/BJJ_CPN.pdf", output_png="Model_visualization/BJJ_CPN.png"):
    """
    Visualiza la red de Petri Coloreada (CPN) usando NetworkX.
    """
    tecnicas_expandidas = expandir_simetria(tecnicas)
    G = nx.DiGraph()

    # --- Crear nodos de Places ---
    places = set()
    for _, _, iniA, iniO, exA, exO, faA, faO in tecnicas_expandidas:
        for p in [iniA, iniO, exA, exO, faA, faO]:
            if p:
                places.add(p)

    for p in sorted(places):
        G.add_node(p, tipo="place")

    # --- Crear nodos de Transiciones ---
    for (id_, nombre, iniA, iniO, exA, exO, faA, faO) in tecnicas_expandidas:
        t_exitoso = f"{id_}_exitoso"
        t_fallido = f"{id_}_fallido"

        subtipo = "A" if "_A" in id_ else "O"
        G.add_node(t_exitoso, tipo="transition", subtipo=f"exitoso_{subtipo}")
        G.add_node(t_fallido, tipo="transition", subtipo=f"fallido_{subtipo}")

        # Arcos
        for src in [iniA, iniO]:
            if src:
                G.add_edge(src, t_exitoso)
                G.add_edge(src, t_fallido)
        for dst in [exA, exO]:
            if dst:
                G.add_edge(t_exitoso, dst)
        for dst in [faA, faO]:
            if dst:
                G.add_edge(t_fallido, dst)

    # --- Layout ---
    pos = nx.spring_layout(G, k=3.2, iterations=250, seed=42)

    # --- Categorías ---
    places_nodes = [n for n, d in G.nodes(data=True) if d["tipo"] == "place"]
    exitosas_nodes = [n for n, d in G.nodes(data=True) if "exitoso" in d.get("subtipo", "")]
    fallidas_nodes = [n for n, d in G.nodes(data=True) if "fallido" in d.get("subtipo", "")]

    plt.figure(figsize=(30, 25))

    # Aristas
    nx.draw_networkx_edges(G, pos, arrows=True, arrowstyle='-|>', arrowsize=15, width=1.5, edge_color="#222", connectionstyle='arc3,rad=0.22',
                            min_source_margin=25, min_target_margin=20)

    # Nodos
    nx.draw_networkx_nodes(G, pos, nodelist=places_nodes, node_color="lightblue",
                           node_shape="o", node_size=2500, edgecolors="black", linewidths=1.5, label="Place")

    nx.draw_networkx_nodes(G, pos, nodelist=exitosas_nodes, node_color="lightgreen",
                           node_shape="s", node_size=1900, edgecolors="darkgreen", linewidths=2.0, label="Transición Exitosa")

    nx.draw_networkx_nodes(G, pos, nodelist=fallidas_nodes, node_color="lightcoral",
                           node_shape="s", node_size=1900, edgecolors="darkred", linewidths=2.0, label="Transición Fallida")

    # Etiquetas
    nx.draw_networkx_labels(G, pos, font_size=8, font_weight="bold")

    # Leyenda
    legend_elements = [
        Patch(facecolor="lightblue", edgecolor="black", label="Place (Estado)"),
        Patch(facecolor="lightgreen", edgecolor="darkgreen", label="Transición Exitosa"),
        Patch(facecolor="lightcoral", edgecolor="darkred", label="Transición Fallida"),
    ]
    plt.legend(handles=legend_elements, loc="upper right", fontsize=10, frameon=True)

    plt.title("Modelo Red de Petri Coloreada (CPN) lucha Brazilian Jiu-Jitsu", fontsize=14, fontweight="bold")
    plt.axis("off")
    plt.tight_layout()

    plt.savefig(output_pdf, format="pdf", bbox_inches="tight")
    plt.savefig(output_png, format="png", bbox_inches="tight", dpi=300)
    plt.close()

    print(f"Red visual guardada en: {output_pdf}")
    print(f"Respaldo en imagen PNG guardado en: {output_png}")


# --- MAIN ---------------------------------------------------------------------

if __name__ == "__main__":
    csv_file = "Input/Grafo_explicito.csv"
    tecnicas = leer_tecnicas(csv_file)

    generar_modelo_petri(tecnicas)
    visualizar_red(tecnicas)
