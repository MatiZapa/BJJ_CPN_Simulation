import csv
import re
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from snakes.nets import *
import json

INPUT_DIR = "Experimentos/Inputs/Caso1.json"
OUTPUT_DIR = "Experimentos/Analisis/Caso de estudio 1"
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

#Carga luchadores
try:
    # Intento de abrir el archivo
    with open(INPUT_DIR, "r", encoding="utf-8") as f:
        luchadores = json.load(f)

    # Validar que existan las claves esperadas para los luchadores
    if "A" not in luchadores or "O" not in luchadores:
        raise KeyError("El archivo JSON no contiene las claves 'A' y 'O' de luchadores necesarias.")

    A = luchadores["A"]
    O = luchadores["O"]

    print("Luchadores cargados correctamente.")

#archivo no encontrado
except FileNotFoundError:
    print(f"ERROR: No se encontró el archivo {INPUT_DIR}. Verifica la ruta.")

#error de formato
except json.JSONDecodeError as e:
    print(f"ERROR en el formato del JSON: {e}")

#error de clave en el archivo
except KeyError as e:
    print(f"ERROR: Falta una clave importante en el archivo JSON: {e}")

#otros errores
except Exception as e:
    print(f"Error inesperado al cargar los luchadores: {e}")

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

def visualizar_red(tecnicas, repertorio_A, repertorio_O,
                   output_pdf=os.path.join(OUTPUT_DIR, "repertorio.pdf"),
                   output_png=os.path.join(OUTPUT_DIR, "repertorio.png")):

    tecnicas_expandidas = expandir_simetria(tecnicas)
    G = nx.DiGraph()

    # -------------------------
    # 1) Construcción del grafo
    # -------------------------

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

        # Guardamos en el nodo el ID original para detectar repertorio
        G.add_node(t_exitoso, tipo="transition", subtipo=f"exitoso_{subtipo}", id_trans=id_)
        G.add_node(t_fallido, tipo="transition", subtipo=f"fallido_{subtipo}", id_trans=id_)

        # Arcos desde estados iniciales
        for src in [iniA, iniO]:
            if src:
                G.add_edge(src, t_exitoso)
                G.add_edge(src, t_fallido)

        # Arcos a estados finales exitosos
        for dst in [exA, exO]:
            if dst:
                G.add_edge(t_exitoso, dst)

        # Arcos a estados finales fallidos
        for dst in [faA, faO]:
            if dst:
                G.add_edge(t_fallido, dst)

    # ----------------------------
    # 2) Detectar places relevantes
    # ----------------------------

    places_A = set()
    places_O = set()

    for (id_, nombre, iniA, iniO, exA, exO, faA, faO) in tecnicas_expandidas:

        prefijo = id_.split("_")[0]  # T01, T02...

        if prefijo in repertorio_A:
            for p in [iniA, iniO, exA, exO, faA, faO]:
                if p:
                    places_A.add(p)

        if prefijo in repertorio_O:
            for p in [iniA, iniO, exA, exO, faA, faO]:
                if p:
                    places_O.add(p)

    # --------------------------------
    # 3) Preparar el layout visual
    # --------------------------------
    pos = nx.spring_layout(G, k=3.2, iterations=250, seed=42)

    plt.figure(figsize=(30, 25))

    # ------------------------
    # 4) Dibujar Aristas
    # ------------------------

    arcos_grises = []
    arcos_negros = []

    for u, v in G.edges():

        # Detectar si corresponde a transición relevante
        color = "#CFCFCF"  # gris por defecto

        if G.nodes[v]["tipo"] == "transition":
            tid = G.nodes[v]["id_trans"].split("_")[0]  # TXX SOLO
            if tid in repertorio_A or tid in repertorio_O:
                color = "black"

        if color == "black":
            arcos_negros.append((u, v))
        else:
            arcos_grises.append((u, v))

    # 4.1 Primero dibujar los grises (fondo)
    nx.draw_networkx_edges(
        G, pos,
        edgelist=arcos_grises,
        arrows=True,
        arrowstyle='-|>',
        arrowsize=15,
        width=1.8,
        edge_color="#CFCFCF",
        connectionstyle='arc3,rad=0.22',
        min_source_margin=25,
        min_target_margin=20
    )

    # 4.2 Luego dibujar los negros (encima)
    nx.draw_networkx_edges(
        G, pos,
        edgelist=arcos_negros,
        arrows=True,
        arrowstyle='-|>',
        arrowsize=15,
        width=2.2,
        edge_color="black",
        connectionstyle='arc3,rad=0.22',
        min_source_margin=25,
        min_target_margin=20
    )


    # ------------------------
    # 5) Dibujar Places
    # ------------------------

    place_colors = []

    for p in places:
        if p in places_A and p in places_O:
            place_colors.append("#9B59B6")  # morado
        elif p in places_A:
            place_colors.append("#FFD700")  # amarillo
        elif p in places_O:
            place_colors.append("#4A90E2")  # azul
        else:
            place_colors.append("#B0B0B0")  # gris

    nx.draw_networkx_nodes(
        G, pos,
        nodelist=list(places),
        node_color=place_colors,
        node_shape="o",
        node_size=2500,
        edgecolors="black",
        linewidths=1.5
    )

    #---------------------------
    # 6) Dibujar Transiciones
    # ---------------------------

    transiciones_grises = []
    transiciones_AO = []  # exitosas + fallidas dentro de repertorios

    for n, d in G.nodes(data=True):
        if d["tipo"] == "transition":
            tid = d["id_trans"].split("_")[0]  # TXX solo

            if tid in repertorio_A or tid in repertorio_O:
                transiciones_AO.append(n)
            else:
                transiciones_grises.append(n)

    # 6.1 Dibujar primero las transiciones grises (fuera de repertorio)
    nx.draw_networkx_nodes(
        G, pos,
        nodelist=transiciones_grises,
        node_color="#D0D0D0",
        node_shape="s",
        node_size=1800,
        edgecolors="gray",
        linewidths=1.5
    )

    # 6.2 Luego dibujar transiciones exitosas relevantes
    exitosas_nodes = [
        n for n in transiciones_AO 
        if "exitoso" in G.nodes[n]["subtipo"]
    ]

    nx.draw_networkx_nodes(
        G, pos,
        nodelist=exitosas_nodes,
        node_color="lightgreen",
        node_shape="s",
        node_size=1900,
        edgecolors="darkgreen",
        linewidths=2.0
    )

    # 6.3 Luego las fallidas relevantes
    fallidas_nodes = [
        n for n in transiciones_AO
        if "fallido" in G.nodes[n]["subtipo"]
    ]

    nx.draw_networkx_nodes(
        G, pos,
        nodelist=fallidas_nodes,
        node_color="lightcoral",
        node_shape="s",
        node_size=1900,
        edgecolors="darkred",
        linewidths=2.0
    )

    nx.draw_networkx_labels(G, pos, font_size=8, font_weight="bold")

    legend_elements = [
        Patch(facecolor="#B0B0B0", edgecolor="black", label="Place fuera de repertorio"),
        Patch(facecolor="#FFD700", edgecolor="black", label="Place Repertorio A"),
        Patch(facecolor="#4A90E2", edgecolor="black", label="Place Repertorio O"),
        Patch(facecolor="#9B59B6", edgecolor="black", label="Place A y O"),
        Patch(facecolor="lightgreen", edgecolor="darkgreen", label="Transición Exitosa"),
        Patch(facecolor="lightcoral", edgecolor="darkred", label="Transición Fallida"),
        Patch(facecolor="black", edgecolor="black", label="Arcos de repertorio"),
        Patch(facecolor="#CFCFCF", edgecolor="black", label="Arcos normales")
    ]

    plt.legend(handles=legend_elements, loc="upper right", fontsize=10, frameon=True)
    plt.title("Modelo Red de Petri Coloreada (CPN) - Brazilian Jiu-Jitsu", fontsize=14, fontweight="bold")
    plt.axis("off")
    plt.tight_layout()

    # Guardar
    plt.savefig(output_pdf, format="pdf", bbox_inches="tight")
    plt.savefig(output_png, format="png", bbox_inches="tight", dpi=300)
    plt.close()

    print(f"Red visual guardada en: {output_pdf}")
    print(f"Respaldo PNG guardado en: {output_png}")

# --- MAIN ---------------------------------------------------------------------

if __name__ == "__main__":
    csv_file = "Input/Grafo_explicito.csv"
    tecnicas = leer_tecnicas(csv_file)
    repertorio_A = A["repertorio"]
    repertorio_O = O["repertorio"]
    visualizar_red(tecnicas,repertorio_A, repertorio_O)