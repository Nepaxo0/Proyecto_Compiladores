from lark import Lark, UnexpectedInput
import tkinter as tk
from tkinter import ttk, scrolledtext, Toplevel
import pickle

# Cargar la gramática desde el archivo
try:
    with open("polux.txt", "r") as file:
        grammar = file.read()
    parser = Lark(grammar, parser="lalr")
    print("Gramática cargada correctamente.")
except Exception as e:
    print(f"Error al cargar la gramática: {e}")
    exit(1)

# Tabla de símbolos con manejo de desbordamiento
class TablaSimbolos:
    def __init__(self, capacidad=100):
        self.capacidad = capacidad
        self.simbolos = []  # Memoria principal
        self.archivo_secundario = "simbolos_overflow.pkl"

    def agregar(self, simbolo):
        if len(self.simbolos) < self.capacidad:
            self.simbolos.append(simbolo)
        else:
            with open(self.archivo_secundario, "ab") as f:
                pickle.dump(simbolo, f)
        print(f"Símbolo agregado: {simbolo}")  # Depuración

    def obtener_todos(self):
        simbolos_totales = self.simbolos[:]
        try:
            with open(self.archivo_secundario, "rb") as f:
                while True:
                    simbolos_totales.append(pickle.load(f))
        except (EOFError, FileNotFoundError):
            pass  # Fin del archivo o archivo no encontrado
        return simbolos_totales

    def limpiar(self):
        self.simbolos.clear()
        open(self.archivo_secundario, "wb").close()  # Vaciar archivo

# Instancia de la tabla de símbolos
tabla_simbolos = TablaSimbolos()

# Función para extraer identificadores y agregarlos a la tabla de símbolos
def extraer_simbolos(tree):
    print("Extrayendo símbolos...")  # Depuración
    for node in tree.iter_subtrees():
        print(f"Nodo: {node.data}")  # Depuración
        if node.data == "declaracion":  # Suponiendo que las declaraciones están bajo este nodo
            nombre = node.children[0].value if len(node.children) > 0 else "Desconocido"
            tipo = node.children[1].value if len(node.children) > 1 else "Desconocido"
            linea = node.meta.line if hasattr(node, 'meta') else "Desconocida"
            
            simbolo = {
                "Identificador": nombre,
                "Categoría": "Variable",
                "Tipo de Dato": tipo,
                "Ámbito": "Global",  # Se puede mejorar
                "Dirección": f"0x{id(nombre):X}",
                "Línea": linea,
                "Valor": "N/A",
                "Estado": "Declarado",
                "Estructura": "N/A",
                "Referencias": 0
            }
            tabla_simbolos.agregar(simbolo)

# Función para el análisis sintáctico con manejo de errores mejorado
def analizador_sintactico(codigo):
    try:
        tabla_simbolos.limpiar()  # Limpiar la tabla antes de cada análisis
        tree = parser.parse(codigo)
        extraer_simbolos(tree)  # Extraer símbolos después del análisis
        return tree, None  # Devuelve el árbol si no hay errores
    except UnexpectedInput as error:
        # Obtener tokens esperados y filtrarlos
        tokens_esperados = error.accepts if hasattr(error, 'accepts') else []
        tokens_legibles = [t for t in tokens_esperados if not t.startswith("__ANON_")]
        tokens_mostrados = ", ".join(tokens_legibles[:5]) + ("..." if len(tokens_legibles) > 5 else "")
        
        error_msg = (f"Error sintáctico en línea {error.line}, columna {error.column}: {str(error)}\n"
                     f"Se esperaba: {tokens_mostrados if tokens_legibles else 'desconocido'}")
        return None, error_msg
    

# Función para analizar código y mostrar errores en la interfaz
def analizar():
    codigo = entrada_texto.get("1.0", tk.END).strip()
    salida_texto.config(state=tk.NORMAL)
    salida_texto.delete("1.0", tk.END)

    tree, error = analizador_sintactico(codigo)
    
    if error:
        salida_texto.insert(tk.END, f"{error}\n", "error")
    else:
        salida_texto.insert(tk.END, "Código válido. Árbol sintáctico generado correctamente.\n", "success")

    salida_texto.config(state=tk.DISABLED)

# Función para mostrar la tabla de símbolos en una nueva ventana
def mostrar_tabla_simbolos():
    ventana_tabla = Toplevel(ventana)
    ventana_tabla.title("Tabla de Símbolos")
    ventana_tabla.geometry("900x400")
    
    tabla = ttk.Treeview(ventana_tabla, columns=("Identificador", "Categoría", "Tipo de Dato", "Ámbito", "Dirección", "Línea", "Valor", "Estado", "Estructura", "Referencias"), show="headings")
    
    encabezados = ["Identificador", "Categoría", "Tipo de Dato", "Ámbito", "Dirección", "Línea", "Valor", "Estado", "Estructura", "Referencias"]
    for h in encabezados:
        tabla.heading(h, text=h)
        tabla.column(h, width=100)
    
    simbolos = tabla_simbolos.obtener_todos()
    print(f"Símbolos en tabla: {simbolos}")  # Depuración
    
    if not simbolos:
        print("⚠️ No se encontraron símbolos para mostrar en la tabla.")
    
    for simbolo in simbolos:
        print(f"Añadiendo símbolo a la tabla: {simbolo}")  # Depuración
        tabla.insert("", "end", values=(simbolo["Identificador"], simbolo["Categoría"], simbolo["Tipo de Dato"],
                                          simbolo["Ámbito"], simbolo["Dirección"], simbolo["Línea"],
                                          simbolo["Valor"], simbolo["Estado"], simbolo["Estructura"], simbolo["Referencias"]))
    
    tabla.pack(expand=True, fill="both")


# Configuración de la interfaz gráfica
ventana = tk.Tk()
ventana.title("Analizador Sintáctico - Polux")
ventana.geometry("900x600")
ventana.configure(bg="#447091")

frame = ttk.Frame(ventana)
frame.pack(padx=20, pady=20, fill="both", expand=True)

etiqueta_entrada = ttk.Label(frame, text="Ingrese el código fuente:")
etiqueta_entrada.pack(anchor="w")

entrada_texto = scrolledtext.ScrolledText(frame, width=90, height=10, font=("Consolas", 10), bg="#ECF0F1")
entrada_texto.pack(pady=5)

boton_analizar = ttk.Button(frame, text="Compilar", command=analizar)
boton_analizar.pack(pady=10)

boton_tabla = ttk.Button(frame, text="Ver Tabla de Símbolos", command=mostrar_tabla_simbolos)
boton_tabla.pack(pady=5)

etiqueta_salida = ttk.Label(frame, text="Resultados del análisis sintáctico:")
etiqueta_salida.pack(anchor="w")

salida_texto = scrolledtext.ScrolledText(frame, width=90, height=10, font=("Consolas", 10), bg="#ECF0F1", state=tk.DISABLED)
salida_texto.pack(pady=5)

salida_texto.tag_configure("error", foreground="red")
salida_texto.tag_configure("success", foreground="green")
salida_texto.tag_configure("info", foreground="blue")

ventana.mainloop()


