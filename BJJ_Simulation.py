import os
from datetime import datetime
import csv
import random
from BJJ_CPN import net
import json
from snakes.nets import Transition
import pandas as pd
import math

#Variables luchadores----------------------------------------------------------------------------------
luchadores = None
A = None
O = None

#CARGA DE DATOS--------------------------------------------------------------------------------------------------------------------
#LUCHADORES

INPUT_DIR = "Experimentos/Inputs/Caso4.json"
OUTPUT_DIR = "Experimentos/Outputs/Caso de estudio 4"
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


#adición de puntaje (no proviene de archivo de entrada)
A["puntaje"] = 0
O["puntaje"] = 0


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

#FUNCIONES ESCENCIALES---------------------------------------------------------------------------------------------------------------------------
#identifica la transición por ID, compara con archivo de técnicas y entrega el tipo de técnica que es (si no encuentra es desconocido)
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

#obtiene la posición actual de los tokens.
def obtener_posiciones():
    posiciones = {"A": None, "O": None}

    for p_name, place in net._place.items():
        tokens = list(place.tokens)
        for token in tokens:
            token_str = str(token).strip().replace("'", "")
            if token_str in posiciones:
                posiciones[token_str] = p_name

    #debug para verificar tokens en consola
    if None in posiciones.values():
        print("Tokens no encontrados en todos los lugares. Posiciones actuales:", posiciones)
    return posiciones

#verifica las transiciones habilitadas dependiendo de donde se encuentren los tokens en la CPN.
def transiciones_habilitadas(actor):
    habilitadas = []

    for t in net.transition():
        nombre = t.name

        # Solo aceptar transiciones 'exitoso'
        if "exitoso" not in nombre:
            continue

        # ==== FILTRO POR ACTOR ====
        if actor == "A" and ("_inv" in nombre):
            continue  # A no puede ejecutar transiciones de O

        if actor == "O" and ("_inv" not in nombre):
            continue  # O no puede ejecutar transiciones de A

        # ==== CHEQUEO DE HABILITACIÓN REAL ====
        try:
            modos = list(t.modes())
            if modos:
                habilitadas.append(t)
        except Exception:
            pass
    return habilitadas

#verifica elementos de lista de transiciones habilitadas con el repertorio en base al ID de técnica, retorna lista con elementos en ambas 
def filtrar_por_repertorio(habilitadas, repertorio):
    filtradas = []                                              #lista para almacenar repertorio filtrado
    repertorio_normalizado = {r.strip() for r in repertorio}    #Pre-normaliza el repertorio (por si vienen con espacios)
    for t in habilitadas:
        nombre = t.name
        id_tecnica = nombre.split("_")[0].strip()               #filtro ID de técnica por caracteres antes del primer _ , ejemplo "T01"
        if id_tecnica in repertorio_normalizado:                #Si el id se encuentra en repertorio, añade a lista filtrada
            filtradas.append(t)

    return filtradas

#calcular iniciativa funciona en base a los atributos de un luchador, combina velocidad y fuerza (promedio), considerando la energía
#se usa luego para ver que luchador hace su ataque primero
def calcular_iniciativa(datos, tecnica):
    # Obtener categoría
    info = info_tecnica(tecnica)
    categoria = info["categoria"].lower()

    # Normalización de categoría
    if categoria in ["derribo", "pase de guardia", "sumisión"]:
        categoria = "ofensiva"
    elif categoria == "escape":
        categoria = "defensiva"
    else:
        categoria = "neutral"

    # Atributos según categoría (promedios)
    if categoria == "ofensiva":
        X = (datos.get("velAt", 0) + datos.get("fueAt", 0)) / 2
    elif categoria == "defensiva":
        X = (datos.get("velDef", 0) + datos.get("fueDef", 0)) / 2
    else:
        X = (
            datos.get("velAt", 0) + datos.get("fueAt", 0) +
            datos.get("velDef", 0) + datos.get("fueDef", 0)
        ) / 4

    # --- Ajuste por categoría ---
    U = 3
    delta = X - U
    k = 0.08  # más suave
    ajuste_categoria = delta * k

    # --- Energía con impacto MUY bajo ---
    energia = datos.get("energy", 100) / 100
    energia_factor = 0.95 + energia * 0.10  # rango 0.95–1.05

    # --- Posición suavizada ---
    pos = datos.get("posicion", "neutral")
    if pos == "dominante":
        pos_factor = 1.03
    elif pos == "inferior":
        pos_factor = 0.97
    else:
        pos_factor = 1.0

    # --- Ruido más fuerte para romper ciclos ---
    ruido = random.uniform(-0.25, 0.25)

    # --- Base MUY COMPRIMIDA ---
    iniciativa = (X / 5) * 0.30 + ajuste_categoria + ruido

    # Factores externos
    iniciativa *= energia_factor
    iniciativa *= pos_factor

    return iniciativa


#permite modificar el gasto de energia de un luchador en base a sus atributos y categoría de técnica a ejecutar
def mod_stamina(actor, tecnica):
    datos_tecnica = info_tecnica(tecnica.name)
    categoria = datos_tecnica["categoria"].lower()
    costo_base = datos_tecnica.get("costo_stamina", 5)  # valor por defecto

    # Normalización de categoría
    if categoria in ["derribo", "pase de guardia", "sumisión"]:
        categoria = "ofensiva"
    elif categoria == "escape":
        categoria = "defensiva"
    else:
        categoria = "neutral"

    # Selección de atributos según categoría
    if categoria == "ofensiva":
        X = (actor.get("velAt", 0) + actor.get("fueAt", 0)) / 2
    elif categoria == "defensiva":
        X = (actor.get("velDef", 0) + actor.get("fueDef", 0)) / 2
    else:  # neutral
        X = (
            actor.get("velAt", 0) + actor.get("fueAt", 0) +
            actor.get("velDef", 0) + actor.get("fueDef", 0)
        ) / 4

    #umbral
    U = 3
    delta = X - U
    #ajuste
    k = 1.3
    if delta > 0:
        A = -int((delta*k).__ceil__())
    elif delta < 0:
        A = int((delta*k).__ceil__())
    else:
        A = 0
    
    #costo final
    costo_final = costo_base + A
    # Siempre al menos 1
    costo_final = max(1, costo_final)

    return costo_final


#probabilidad de exito toma atributos de luchador y categoria y define si una técnica es exitosa o fallida, retorna bool.
def prob_exito(actor, tecnica):
    nombre_tec = tecnica.name
    datos_tecnica = info_tecnica(nombre_tec)
    categoria = datos_tecnica["categoria"]
    #normalizacion decategoria 
    if categoria.lower() in ["derribo", "pase de guardia", "sumisión"]:
        categoria = "ofensiva"
    elif categoria.lower() == "escape":
        categoria = "defensiva"
    else:
        categoria = "neutral"
    #seleción de T segun categoria
    if categoria.lower() == "ofensiva":
        T = (actor.get("velAt", 0) + actor.get("fueAt", 0)) / 10
    elif categoria.lower() == "defensiva":
        T = (actor.get("velDef", 0) + actor.get("fueDef", 0)) / 10
    elif categoria.lower() == "neutral":
        T = (actor.get("velAt", 0) + actor.get("fueAt", 0) +
             actor.get("velDef", 0) + actor.get("fueDef", 0)) / 20
    else:
        raise ValueError("Categoría de técnica no válida.")
    
    E = actor.get("energy", 0) / 100
    #si por abc motivo la energia bajara extremadamente bajo cero, lo toma como 1.
    if E < 0:
        E = 0.1 
    P = (T * E) * 0.8
    n = random.random()
    return n < P


#ejecución de técnica selecionada y retorna el resultado de exito o fallo
def ejecutar_tecnica(actor_dict, tecnica, tiempo_simulacion):
    nombre = tecnica.name  # ej: "T26_exitoso"
    
    # Obtener datos desde el grafo
    datos = info_tecnica(nombre) #trae los datos de la técnica por ID
    tiempo_posicion = datos["tiempo_posicion"]
    categoria = datos["categoria"]
    costo_stamina = mod_stamina(actor_dict, tecnica) #se calcula con la función de modificación
    tiempo_ejec = datos["tiempo_ejecucion_s"]
    puntaje = datos["puntaje"]
    
    #genera un numero randomico entre el 20%+- del tiempo en posición, para despues comparar y poder asignar el puntaje
    random_posicion = random.uniform((tiempo_posicion*0.8),(tiempo_posicion*1.2))
    
    #truncamos si es menor redondeamos si es mayor (para manejar numeros enteros)
    if random_posicion >= tiempo_posicion:
        random_ajustado = round(random_posicion)
    else:
        random_ajustado = math.floor(random_posicion)

    #REVISION DE SUMISION, SOLO SE EJECUTA LA SUMISION EXITOSA SI LA TECNICA LOGRA SER MANTENIDA MAS QUE EL TIEMPO PROMEDIO DEFINIDO EN EL GRAFO
    if categoria == "Sumisión" and prob_exito(actor_dict, tecnica):
        if random_posicion >= tiempo_posicion:
            net.transition(nombre).fire(frozenset())    #dispara transición
            actor_dict["energy"] -= costo_stamina       #resta stamina
            tiempo_simulacion += tiempo_ejec            #suma tiempo ejecucion
            tiempo_simulacion += random_ajustado
            return "exito", nombre, tiempo_simulacion, random_ajustado       #suma tiempo de mantencion de tecnica
        else:
            nombre_fallida = nombre.replace("_exitoso", "_fallido")             #cambia a la version fallida de la sumisión 
            net.transition(nombre_fallida).fire(frozenset())                    #dispara la version fallida
            return "fallo", nombre, tiempo_simulacion, random_ajustado
    
    #EJECUCION DE TECNICA QUE NO ES DE SUMISION
    if prob_exito(actor_dict, tecnica):  # ÉXITO
        net.transition(nombre).fire(frozenset())
        #siempre resta energia y suma el tiempo de ejecución
        actor_dict["energy"] -= costo_stamina                   #resta energia
        tiempo_simulacion += tiempo_ejec                        #suma tiempo de ejecución
        #asigna puntaje solo si matuvo la posición mas que el tiempo promedio definido
        if random_posicion >= tiempo_posicion:
            actor_dict["puntaje"] += puntaje
        tiempo_simulacion += random_ajustado                    #suma tiempo que mantuvo la posicion
        return "exito", nombre, tiempo_simulacion, random_ajustado

    else:  # FALLO
        nombre_fallida = nombre.replace("_exitoso", "_fallido")

        try:
            net.transition(nombre_fallida).fire(frozenset())

            actor_dict["energy"] -= int(costo_stamina * 0.7)            #reduce la energia, pero solo un 70% del costo
            tiempo_simulacion += tiempo_ejec                            #suma tiempo de ejecución
            tiempo_simulacion += random_ajustado                        #suma tiempo que mantuvo la posición
            return "fallo", nombre_fallida, tiempo_simulacion, random_ajustado

        except Exception:
            # Si no existe transición fallida, fallar sin mover posiciones
            actor_dict["energy"] -= int(costo_stamina * 0.5)
            tiempo_simulacion += 1

            return "fallo", nombre, tiempo_simulacion, random_ajustado


#SIMULACIÓN PRINCIPAL-------------------------------------------------------------------------------------------
tiempo = 0 #tiempo de simulación
max_pasos = 6 * 60 #maximo de pasos de simulacion = 6 minutos si lo tomamos como segundo 
registro = [] #log

while tiempo < max_pasos: #mientras no se supere el máximo de pasos
    #transiciones habilitadas sin filtro
    habilitadas_A = transiciones_habilitadas("A")
    habilitadas_O = transiciones_habilitadas("O")

    #filtro repertorio
    habilitadas_A = filtrar_por_repertorio(habilitadas_A, A["repertorio"])
    habilitadas_O = filtrar_por_repertorio(habilitadas_O, O["repertorio"])

    #verificación si existen técnicas para disparar, si no existen se finaliza la simulación.
    if not habilitadas_A and not habilitadas_O:
        print("No quedan transiciones habilitadas. Fin de la simulación.")
        break

    # Ambos intentan actuar simultaneamente, se selecciona una técnica de las habilitadas, pero no se ejecuta aún
    tecnica_A = random.choice(habilitadas_A) if habilitadas_A else None
    tecnica_O = random.choice(habilitadas_O) if habilitadas_O else None

    # Calcular iniciativa, para ver cual de los actores efectúa la técnica, si no hay tecnica iniciativa = 0
    iniciativa_A = calcular_iniciativa(A,tecnica_A) if tecnica_A else -1
    iniciativa_O = calcular_iniciativa(O,tecnica_O) if tecnica_O else -1
    print(f"iniciativa A: {iniciativa_A}, Iniciativa O: {iniciativa_O}")
    #decisión de quien actúa primero, el que lo haga será quien finalmente ejecute la técnica, el segundo no ejecutará su técnica
    #esto debido a que si alguien ejecuta su técnica, fallida o exitosa, cambia la posición del oponente y la propia
    if iniciativa_A > iniciativa_O and tecnica_A:
        actor = "A"
        tecnica = tecnica_A
        actor_dict = A
    else:
        actor = "O"
        tecnica = tecnica_O
        actor_dict = O

    # Ejecutar técnica del actor con mayor iniciativa
    resultado, tecnica_final, tiempo, mantencion = ejecutar_tecnica(actor_dict, tecnica, tiempo)

    # Obtener posiciones actuales
    posiciones = obtener_posiciones()
    posA = posiciones["A"]
    posO = posiciones["O"]

    # Registrar evento
    registro.append({
        "tiempo": tiempo,
        "actor": actor,
        "tecnica": tecnica_final,
        "resultado": resultado,
        "pos_A": posA,
        "pos_O": posO,
        "mantencion": mantencion,
        "puntaje_A": A["puntaje"],
        "puntaje_O": O["puntaje"]
    })

    #Detección de Sumisión---------------------------------
    #estandarización de texto a minusculas
    datos_tecnica = info_tecnica(tecnica_final)
    tipo = datos_tecnica["categoria"]
    if tipo.lower() == "sumisión" and resultado == "exito":
        print(f"Sumisión detectada: {tecnica_final}. Combate terminado.")
        print(f"Ganador: {actor}")
        print(f"Ténica de sumisión: {tecnica_final}")
        # Registrar último estado antes de cortar
        break


#GUARDAR REGISTRO EN CSV---------------------------------------------------------------------------------
os.makedirs("Output", exist_ok=True)                            #crea directorio si no existe
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")            #formato año/mes/dia/hora/min/seg
filename = f"registro_bjj_{timestamp}.csv"                      #nombre del archivo
filepath = os.path.join(OUTPUT_DIR, filename)                     #ruta del archivo

with open(filepath, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["tiempo", "actor", "tecnica", "resultado", "mantencion", "pos_A", "pos_O", "puntaje_A", "puntaje_O"]
    )
    writer.writeheader()
    writer.writerows(registro)

print(f"Simulación Completa, Registro guardado en: {filepath}")
