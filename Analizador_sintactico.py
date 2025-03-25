from lark import Lark, UnexpectedInput
import tkinter as tk
from tkinter import ttk, scrolledtext, Toplevel
from lark import Lark, UnexpectedInput, Tree, Token
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

# Algoritmo de Shunting Yard para evaluar expresiones matemáticas
def shunting_yard(expresion):
    precedencia = {"+": 1, "-": 1, "*": 2, "/": 2, "^": 3}
    salida = []
    operadores = []
    tokens = expresion.split()
    
    for token in tokens:
        if token.isnumeric():
            salida.append(token)
        elif token in precedencia:
            while (operadores and operadores[-1] in precedencia and
                   precedencia[operadores[-1]] >= precedencia[token]):
                salida.append(operadores.pop())
            operadores.append(token)
        elif token == "(":
            operadores.append(token)
        elif token == ")":
            while operadores and operadores[-1] != "(":
                salida.append(operadores.pop())
            operadores.pop()
    
    while operadores:
        salida.append(operadores.pop())
    
    return " ".join(salida)

# Función para extraer identificadores y agregarlos a la tabla de símbolos
def extraer_simbolos(parse_tree):  # Cambié el parámetro de nombre para evitar confusión
    print("Extrayendo símbolos del árbol sintáctico...")
    
    def get_value(node):
        """Función auxiliar para obtener el valor de un nodo"""
        if isinstance(node, Tree):
            # Para árboles, obtenemos el valor del primer hijo
            return get_value(node.children[0]) if node.children else ""
        elif isinstance(node, Token):
            return node.value
        return str(node)
    
    for node in parse_tree.iter_subtrees():
        print(f"Procesando nodo: {node.data}")  # Debug
        
        try:
            # Declaraciones de variables
            if node.data == "variable_declaration":
                if len(node.children) >= 1:
                    nombre = get_value(node.children[0])
                    valor = get_value(node.children[1]) if len(node.children) > 1 else "N/A"
                    
                    simbolo = {
                        "Identificador": nombre,
                        "Categoría": "Variable",
                        "Tipo de Dato": "inferido",
                        "Ámbito": "Global",
                        "Dirección": f"0x{id(nombre):X}",
                        "Línea": getattr(node.meta, 'line', 'Desconocida'),
                        "Valor": valor,
                        "Estado": "Declarado",
                        "Estructura": "N/A",
                        "Referencias": 0
                    }
                    tabla_simbolos.agregar(simbolo)
            
            # Declaraciones de funciones
            elif node.data == "function_declaration":
                if len(node.children) >= 1:
                    nombre = get_value(node.children[0])
                    
                    simbolo = {
                        "Identificador": nombre,
                        "Categoría": "Función",
                        "Tipo de Dato": "Función",
                        "Ámbito": "Global",
                        "Dirección": f"0x{id(nombre):X}",
                        "Línea": getattr(node.meta, 'line', 'Desconocida'),
                        "Valor": "N/A",
                        "Estado": "Definido",
                        "Estructura": "N/A",
                        "Referencias": 0
                    }
                    tabla_simbolos.agregar(simbolo)
            
            # Declaraciones de clases
            elif node.data == "class_declaration":
                if len(node.children) >= 1:
                    nombre = get_value(node.children[0])
                    
                    simbolo = {
                        "Identificador": nombre,
                        "Categoría": "Clase",
                        "Tipo de Dato": "Clase",
                        "Ámbito": "Global",
                        "Dirección": f"0x{id(nombre):X}",
                        "Línea": getattr(node.meta, 'line', 'Desconocida'),
                        "Valor": "N/A",
                        "Estado": "Definido",
                        "Estructura": "N/A",
                        "Referencias": 0
                    }
                    tabla_simbolos.agregar(simbolo)
                    
        except Exception as e:
            print(f"Error procesando nodo {node.data}: {e}")
            continue

        
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

    # Limpiar tabla antes de cada análisis
    tabla_simbolos.limpiar()
    
    try:
        tree = parser.parse(codigo)
        salida_texto.insert(tk.END, "Análisis sintáctico exitoso!\n", "success")
        salida_texto.insert(tk.END, "Estructura del árbol:\n" + tree.pretty() + "\n\n", "info")
        
        # Extraer símbolos
        extraer_simbolos(tree)
        
        # Mostrar estadísticas
        simbolos = tabla_simbolos.obtener_todos()
        salida_texto.insert(tk.END, f"Símbolos encontrados: {len(simbolos)}\n", "info")
        
    except UnexpectedInput as e:
        error_msg = f"Error en línea {e.line}:{e.column} - {e.get_context(codigo)}"
        salida_texto.insert(tk.END, error_msg, "error")
    
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


