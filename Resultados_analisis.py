import pandas as pd
import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

#NUMERO DE CASO DE ESTUDIO (PARA OUTPUT)
caso = "Caso de estudio 4"

#CARGA DE GRAFO TECNICAS
try:
    #selección de columnas relevantes
    grafo_exp = pd.read_csv(
        "Input/Grafo_Explicito.csv",
        usecols=["ID", "Categoría", "Tiempo Posición", "Costo Stamina", "Tiempo Ejecución", "Puntaje"]
    )

    #normalización de datos.
    grafo_exp["ID"] = grafo_exp["ID"].astype(str).str.strip()
    grafo_exp["Categoría"] = grafo_exp["Categoría"].astype(str).str.lower().str.strip()
    
    # Conversión de columnas numéricas a int
    for col in ["Tiempo Posición", "Costo Stamina", "Tiempo Ejecución", "Puntaje"]:
        grafo_exp[col] = (
            grafo_exp[col]
            .fillna(0)              # si hay valores vacíos pone 0
            .astype(float)          # primero pasar a float por si vienen como texto
            .astype(int)            # finalmente int
        )
    #debug
    print("Carga de archivo con técnicas correcta")

except Exception as e:
    print(f"No se pudo cargar el archivo de técnicas: {e}")
    grafo_exp = None

def info_tecnica(nombre_transicion):
    if grafo_exp is None:
        return {
            "tiempo_posicion": 0,
            "categoria": "desconocida",
            "costo_stamina": 0,
            "tiempo_ejecucion_s": 0,
            "puntaje": 0
        }

    # Extraer ID antes del primer "_"
    try:
        id_tecnica = nombre_transicion.split("_")[0]
    except Exception:
        id_tecnica = None

    if not id_tecnica:
        return {
            "tiempo_posicion": 0,
            "categoria": "desconocida",
            "costo_stamina": 0,
            "tiempo_ejecucion_s": 0,
            "puntaje": 0
        }

    fila = grafo_exp[grafo_exp["ID"] == id_tecnica]

    if fila.empty:
        return {
            "tiempo_posicion": 0,
            "categoria": "desconocida",
            "costo_stamina": 0,
            "tiempo_ejecucion_s": 0,
            "puntaje": 0
        }

    fila = fila.iloc[0]

    return {
        "tiempo_posicion": fila["Tiempo Posición"],
        "categoria": fila["Categoría"],
        "costo_stamina": int(fila["Costo Stamina"]),
        "tiempo_ejecucion_s": int(fila["Tiempo Ejecución"]),
        "puntaje": int(fila["Puntaje"])
    }

# =========================
# RUTAS DEL PROYECTO
# =========================

BASE_INPUT_DIR = os.path.join(
    "Experimentos", "Outputs", caso
)

BASE_OUTPUT_DIR = os.path.join(
    "Experimentos", "Analisis", caso
)

os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)


#FUNCION DETECTAR SUMISION
def detectar_victoria_sumision(df):
        for _, row in df.iterrows():
            if row["resultado"] != "exito":
                continue
            info = info_tecnica(row["tecnica"])
            if info["categoria"] == "sumisión":
                return row["actor"]
        return None


# =========================
# FUNCIÓN PRINCIPAL
# =========================
def analyze_folder(input_dir, output_dir):

    csv_files = glob.glob(os.path.join(input_dir, "*.csv"))

    if not csv_files:
        raise RuntimeError("No se encontraron archivos CSV en la ruta definida.")

    per_file_metrics = []
    heatmap_data = {"A": {}, "O": {}}

    # =========================
    # CONTADORES GLOBALES DE VICTORIAS
    # =========================
    victorias_sum_A = 0
    victorias_sum_O = 0
    victorias_puntos_A = 0
    victorias_puntos_O = 0


    # =========================
    # PROCESAMIENTO POR ARCHIVO
    # =========================
    for file in csv_files:
        df = pd.read_csv(file)

        # Duración del combate
        tiempo_total = df["tiempo"].iloc[-1]

        # Puntaje final
        puntaje_A = df["puntaje_A"].iloc[-1]
        puntaje_O = df["puntaje_O"].iloc[-1]

        # --- Varianza de puntaje interna (fluctuación dentro del combate)
        var_puntaje_A = df["puntaje_A"].var()
        var_puntaje_O = df["puntaje_O"].var()

        # Mantención promedio por actor
        mant_A = df[df["actor"] == "A"]["mantencion"]
        mant_O = df[df["actor"] == "O"]["mantencion"]

        prom_mant_A = mant_A.mean() if not mant_A.empty else 0
        prom_mant_O = mant_O.mean() if not mant_O.empty else 0

        # Efectividad por actor
        acciones_A = df[df["actor"] == "A"]
        acciones_O = df[df["actor"] == "O"]

        efec_A = (
            (acciones_A["resultado"] == "exito").sum() / len(acciones_A)
            if len(acciones_A) > 0 else 0
        )
        efec_O = (
            (acciones_O["resultado"] == "exito").sum() / len(acciones_O)
            if len(acciones_O) > 0 else 0
        )
         # --- Detección de victoria
        ganador_sumision = detectar_victoria_sumision(df)

        # =========================
        # CONTEO DE VICTORIAS (SUMISIÓN / PUNTOS)
        # =========================
        if ganador_sumision == "A":
            victorias_sum_A += 1
        elif ganador_sumision == "O":
            victorias_sum_O += 1
        else:
            # Victoria por puntos (o empate)
            if puntaje_A > puntaje_O:
                victorias_puntos_A += 1
            elif puntaje_O > puntaje_A:
                victorias_puntos_O += 1        

        # Datos para heatmap
        for _, row in df.iterrows():
            actor = row["actor"]
            tecnica = row["tecnica"].split("_")[0]

            heatmap_data.setdefault(actor, {})
            heatmap_data[actor][tecnica] = heatmap_data[actor].get(tecnica, 0) + 1

        per_file_metrics.append({
            "archivo": os.path.basename(file),
            "tiempo_combate": tiempo_total,
            "puntaje_A": puntaje_A,
            "puntaje_O": puntaje_O,
            "var_puntaje_A": var_puntaje_A,
            "var_puntaje_O": var_puntaje_O,
            "mantencion_A": prom_mant_A,
            "mantencion_O": prom_mant_O,
            "efectividad_A": efec_A * 100,
            "efectividad_O": efec_O * 100
        })

    df_summary = pd.DataFrame(per_file_metrics)

    # =========================
    # DDESVIACIÓN ESTANDAR ENTRE COMBATES
    # =========================
    std_tiempo_combates = df_summary["tiempo_combate"].std(ddof=0)

    std_puntaje_A_combates = df_summary["puntaje_A"].std(ddof=0)
    std_puntaje_O_combates = df_summary["puntaje_O"].std(ddof=0)

    # =========================
    # VICTORIAS TOTALES Y PROBABILIDAD
    # =========================
    victorias_A = victorias_sum_A + victorias_puntos_A
    victorias_O = victorias_sum_O + victorias_puntos_O

    total_victorias = victorias_A + victorias_O

    prob_sumision_A = (victorias_sum_A / victorias_A * 100) if victorias_A > 0 else 0
    prob_sumision_O = (victorias_sum_O / victorias_O * 100) if victorias_O > 0 else 0

    prob_victoria_A = (victorias_A / total_victorias * 100) if total_victorias > 0 else 0
    prob_victoria_O = (victorias_O / total_victorias * 100) if total_victorias > 0 else 0

    # =========================
    # MÉTRICAS GLOBALES
    # =========================
    metrics = {
        "tiempo_promedio": df_summary["tiempo_combate"].mean(),
        "std_tiempo_combates": std_tiempo_combates,
        "victorias_A": victorias_A,
        "victorias_O": victorias_O,
        "victorias_sum_A": victorias_sum_A,
        "victorias_sum_O": victorias_sum_O,
        "victorias_puntos_A": victorias_puntos_A,
        "victorias_puntos_O": victorias_puntos_O,
        "prob_victoria_A_pct": prob_victoria_A,
        "prob_victoria_O_pct": prob_victoria_O,
        "prob_sumision_A": prob_sumision_A,
        "prob_sumision_O": prob_sumision_O,
        "puntaje_A_prom": df_summary["puntaje_A"].mean(),
        "puntaje_O_prom": df_summary["puntaje_O"].mean(),
        "std_puntaje_A_combates": std_puntaje_A_combates,
        "std_puntaje_O_combates": std_puntaje_O_combates,
        "mantencion_A_prom": df_summary["mantencion_A"].mean(),
        "mantencion_O_prom": df_summary["mantencion_O"].mean(),
        "coef_var_mant_A": (
            df_summary["mantencion_A"].std(ddof=0) /
            df_summary["mantencion_A"].mean()
            if df_summary["mantencion_A"].mean() > 0 else 0
        ),
        "coef_var_mant_O": (
            df_summary["mantencion_O"].std(ddof=0) /
            df_summary["mantencion_O"].mean()
            if df_summary["mantencion_O"].mean() > 0 else 0
        ),
        "efectividad_A_prom": df_summary["efectividad_A"].mean(),
        "efectividad_O_prom": df_summary["efectividad_O"].mean()
    }





    df_metrics = pd.DataFrame([metrics])

    # =========================
    # GUARDADO CSV
    # =========================
    df_summary.to_csv(
        os.path.join(output_dir, f"resumen_por_archivo.csv"),
        index=False
    )
    df_metrics.to_csv(
        os.path.join(output_dir, f"metricas_general.csv"),
        index=False
    )

    # =========================
    # BOXPLOT – TIEMPOS
    # =========================
    plt.figure()
    plt.boxplot(df_summary["tiempo_combate"], vert=False)
    plt.title("Distribución del tiempo de combate")
    plt.xlabel("Tiempo")
    plt.savefig(
        os.path.join(output_dir, f"boxplot_tiempo.png")
    )
    plt.close()

    # =========================
    # HEATMAP TRANSICIONES
    # =========================
    heatmap_df = pd.DataFrame(heatmap_data).fillna(0)

    plt.figure(figsize=(10, 6))
    plt.imshow(heatmap_df, aspect="auto")
    plt.colorbar(label="Frecuencia")
    plt.xticks(range(len(heatmap_df.columns)), heatmap_df.columns)
    plt.yticks(range(len(heatmap_df.index)), heatmap_df.index)
    plt.title("Mapa de calor de transiciones por actor")
    plt.savefig(
        os.path.join(output_dir, f"heatmap_transiciones.png")
    )
    plt.close()

    # =========================
    # BARRA VICTORIAS TOTALES
    # =========================

    plt.figure()
    plt.bar(["A", "O"], [victorias_A, victorias_O],color=["blue", "red"])
    plt.title("Victorias totales por luchador")
    plt.ylabel("Cantidad de victorias")
    plt.savefig(
        os.path.join(output_dir, f"victorias_totales.png")
    )
    plt.close()


    # =========================
    # BARRA VICTORIAS A/O
    # =========================
    
    labels = ["Sumisión", "Puntos"]

    # Luchador A
    plt.figure()
    plt.bar(labels, [victorias_sum_A, victorias_puntos_A])
    plt.title("Distribución de victorias – Luchador A")
    plt.ylabel("Cantidad")
    plt.savefig(
        os.path.join(output_dir, f"victorias_tipo_A.png")
    )
    plt.close()

    # Luchador O
    plt.figure()
    plt.bar(labels, [victorias_sum_O, victorias_puntos_O])
    plt.title("Distribución de victorias – Luchador O")
    plt.ylabel("Cantidad")
    plt.savefig(
        os.path.join(output_dir, f"victorias_tipo_O.png")
    )
    plt.close()

# ======================================================
    # 🔵 NUEVO: GRÁFICO DE BARRAS – PUNTAJE PROMEDIO A vs O
    # ======================================================
    plt.figure()
    plt.bar(["A", "O"],
            [metrics["puntaje_A_prom"], metrics["puntaje_O_prom"]],
            color=["blue", "red"])
    plt.title("Puntaje promedio por luchador")
    plt.ylabel("Puntaje promedio")
    plt.savefig(
        os.path.join(output_dir, "puntaje_promedio_comparacion.png")
    )
    plt.close()

    # ============================================================
    # 🔵 NUEVO: GRÁFICO DE BARRAS – MANTENCIÓN PROMEDIO A vs O
    # ============================================================
    plt.figure()
    plt.bar(["A", "O"],
            [metrics["mantencion_A_prom"], metrics["mantencion_O_prom"]],
            color=["blue", "red"])
    plt.title("Mantención promedio por luchador")
    plt.ylabel("Mantención promedio")
    plt.savefig(
        os.path.join(output_dir, "mantencion_promedio_comparacion.png")
    )
    plt.close()


    # =========================
    # RADAR COMPARATIVO (A vs O)
    # =========================

    labels = [
        "Prob. Victoria (%)",
        "STD Puntaje",
        "Mantención Prom",
        "Prob. Sumisión (%)",
        "Efectividad (%)"
    ]

    # Valores para A
    values_A = [
        metrics["prob_victoria_A_pct"],
        metrics["std_puntaje_A_combates"],
        metrics["mantencion_A_prom"],
        metrics["prob_sumision_A"],
        metrics["efectividad_A_prom"]
    ]

    # Valores para O
    values_O = [
        metrics["prob_victoria_O_pct"],
        metrics["std_puntaje_O_combates"],
        metrics["mantencion_O_prom"],
        metrics["prob_sumision_O"],
        metrics["efectividad_O_prom"]
    ]

    # Normalizar mínimamente (>= 0)
    values_A = [v if v >= 0 else 0 for v in values_A]
    values_O = [v if v >= 0 else 0 for v in values_O]

    # Número de variables
    N = len(labels)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()

    # Cerrar polígonos
    values_A += values_A[:1]
    values_O += values_O[:1]
    angles += angles[:1]

    # Crear figura
    plt.figure(figsize=(8, 8))
    ax = plt.subplot(111, polar=True)

    # Serie A
    ax.plot(angles, values_A, color="blue", linewidth=2, label="Luchador A")
    ax.fill(angles, values_A, color="blue", alpha=0.25)

    # Serie O
    ax.plot(angles, values_O, color="red", linewidth=2, label="Luchador O")
    ax.fill(angles, values_O, color="red", alpha=0.25)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_title("Comparación de desempeño: Luchador A vs Luchador O", y=1.08)

    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

    radar_filename = os.path.join(output_dir, "radar_comparativo_A_vs_O.png")
    plt.tight_layout()
    plt.savefig(radar_filename)
    plt.close()


# =========================
# EJECUCIÓN
# =========================
if __name__ == "__main__":
    analyze_folder(BASE_INPUT_DIR, BASE_OUTPUT_DIR)
