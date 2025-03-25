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
def extraer_simbolos(tree, ambito="Global"):
    simbolos = []
    variables_globales = set()
    
    def get_identifier(node):
        """Obtiene el identificador completo"""
        if isinstance(node, Token):
            return node.value
        return ''.join(get_identifier(child) for child in node.children)

    def get_line(node):
        """Obtiene la línea de declaración"""
        try:
            return node.meta.line if hasattr(node, 'meta') and hasattr(node.meta, 'line') else 'N/A'
        except:
            return 'N/A'

    for node in tree.iter_subtrees():
        current_line = get_line(node)

        # Variables globales
        if node.data == "variable_declaration" and ambito == "Global":
            if len(node.children) < 1:
                continue
                
            identificador = get_identifier(node.children[0])
            if identificador in variables_globales:
                continue
                
            variables_globales.add(identificador)
            tipo = "desconocido"
            valor = "N/A"
            
            if len(node.children) > 1:
                val_node = node.children[1]
                if isinstance(val_node, Token):
                    if val_node.type in ('NUMBER', 'INTEGER'):
                        tipo = 'int' if '.' not in val_node.value else 'float'
                        valor = val_node.value
                    elif val_node.type == 'STRING_LITERAL':
                        tipo = 'string'
                        valor = val_node.value
                    elif val_node.type == 'BOOLEAN':
                        tipo = 'bool'
                        valor = val_node.value
            
            simbolos.append({
                "Identificador": identificador,
                "Categoría": "Variable",
                "Tipo de Dato": tipo,
                "Ámbito": ambito,
                "Dirección": f"0x{abs(hash(f'{identificador}{ambito}')):X}",
                "Línea": current_line,
                "Valor": valor,
                "Estado": "Inicializado" if valor != "N/A" else "Declarado",
                "Estructura": "Simple",
                "Referencias": 0
            })

        # Funciones
        elif node.data == "function_declaration":
            if len(node.children) < 1:
                continue
                
            identificador = get_identifier(node.children[0])
            params = []
            
            if len(node.children) > 1 and hasattr(node.children[1], 'data') and node.children[1].data == 'parameter_list':
                params = [get_identifier(p.children[0]) for p in node.children[1].find_data('parameter')]
            
            simbolos.append({
                "Identificador": identificador,
                "Categoría": "Función",
                "Tipo de Dato": f"Función({', '.join(params)})",
                "Ámbito": ambito,
                "Dirección": f"0x{abs(hash(identificador)):X}",
                "Línea": current_line,
                "Valor": f"Parámetros: {', '.join(params)}",
                "Estado": "Definido",
                "Estructura": "N/A",
                "Referencias": 0
            })
            
            # Procesar parámetros
            for param in params:
                simbolos.append({
                    "Identificador": param,
                    "Categoría": "Variable",
                    "Tipo de Dato": "desconocido",
                    "Ámbito": identificador,
                    "Dirección": f"0x{abs(hash(f'{param}{identificador}')):X}",
                    "Línea": current_line,
                    "Valor": "N/A",
                    "Estado": "Declarado",
                    "Estructura": "Simple",
                    "Referencias": 0
                })
            
            # Procesar cuerpo de función
            if len(node.children) > (2 if len(params) > 0 else 1):
                cuerpo = node.children[2] if len(params) > 0 else node.children[1]
                extraer_simbolos(cuerpo, identificador)

        # Clases
        elif node.data == "class_declaration":
            if len(node.children) < 1:
                continue
                
            identificador = get_identifier(node.children[0])
            simbolos.append({
                "Identificador": identificador,
                "Categoría": "Clase",
                "Tipo de Dato": "class",
                "Ámbito": ambito,
                "Dirección": f"0x{abs(hash(identificador)):X}",
                "Línea": current_line,
                "Valor": "N/A",
                "Estado": "Definido",
                "Estructura": "N/A",
                "Referencias": 0
            })
            
            # Procesar atributos de clase
            if len(node.children) > 1:
                for child in node.children[1].find_data('variable_declaration'):
                    if len(child.children) < 1:
                        continue
                        
                    attr_id = get_identifier(child.children[0])
                    simbolos.append({
                        "Identificador": attr_id,
                        "Categoría": "Variable",
                        "Tipo de Dato": "desconocido",
                        "Ámbito": identificador,
                        "Dirección": f"0x{abs(hash(f'{attr_id}{identificador}')):X}",
                        "Línea": get_line(child),
                        "Valor": "N/A",
                        "Estado": "Declarado",
                        "Estructura": "Simple",
                        "Referencias": 0
                    })
    
    return simbolos

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
    # Obtener el código fuente del área de texto
    codigo = entrada_texto.get("1.0", tk.END).strip()
    
    # Configurar el widget de salida
    salida_texto.config(state=tk.NORMAL)
    salida_texto.delete("1.0", tk.END)
    
    # Verificar si hay código para analizar
    if not codigo:
        salida_texto.insert(tk.END, "Error: No hay código para analizar\n", "error")
        salida_texto.config(state=tk.DISABLED)
        return
    
    try:
        # Realizar el análisis sintáctico
        arbol = parser.parse(codigo)
        
        # Mostrar éxito en el análisis
        salida_texto.insert(tk.END, "✓ Análisis sintáctico completado con éxito\n\n", "success")
        
        # Mostrar el árbol sintáctico (formateado)
        salida_texto.insert(tk.END, "Árbol sintáctico generado:\n", "info")
        salida_texto.insert(tk.END, arbol.pretty(), "info")
        salida_texto.insert(tk.END, "\n\n")
        
        # Extraer símbolos y mostrar estadísticas
        simbolos = extraer_simbolos(arbol)
        salida_texto.insert(tk.END, f"Se encontraron {len(simbolos)} símbolos en el código\n", "info")
        
        # Actualizar la tabla de símbolos global
        global tabla_simbolos
        tabla_simbolos.limpiar()
        for simbolo in simbolos:
            tabla_simbolos.agregar(simbolo)
        
        # Mostrar resumen de categorías
        categorias = {}
        for s in simbolos:
            categorias[s["Categoría"]] = categorias.get(s["Categoría"], 0) + 1
        
        salida_texto.insert(tk.END, "Resumen por categorías:\n", "info")
        for cat, cantidad in categorias.items():
            salida_texto.insert(tk.END, f"- {cat}: {cantidad}\n", "info")
    
    except UnexpectedInput as e:
        # Manejar errores sintácticos
        error_msg = f"✗ Error sintáctico en línea {e.line}, columna {e.column}:\n"
        error_msg += f"Contexto: {e.get_context(codigo)}\n"
        error_msg += f"Se esperaba: {', '.join(e.accepts) if hasattr(e, 'accepts') else 'desconocido'}\n"
        
        salida_texto.insert(tk.END, error_msg, "error")
        
        # Resaltar el error en el código
        inicio = f"{e.line}.{e.column}"
        fin = f"{e.line}.{e.column + 5}"
        entrada_texto.tag_add("error", inicio, fin)
        entrada_texto.tag_config("error", background="red", foreground="white")
    
    except Exception as e:
        # Manejar otros errores inesperados
        salida_texto.insert(tk.END, f"Error inesperado: {str(e)}\n", "error")
    
    finally:
        # Deshabilitar la edición del widget de salida
        salida_texto.config(state=tk.DISABLED)

# Función para mostrar la tabla de símbolos en una nueva ventana
def mostrar_tabla_simbolos():
    try:
        ventana_tabla = Toplevel(ventana)
        ventana_tabla.title("Tabla de Símbolos")
        ventana_tabla.geometry("1200x600")
        
        # Obtener el código actual
        codigo = entrada_texto.get("1.0", tk.END).strip()
        if not codigo:
            tk.Label(ventana_tabla, text="No hay código para analizar", fg="red").pack()
            return
        
        # Parsear y extraer símbolos
        arbol = parser.parse(codigo)
        simbolos = extraer_simbolos(arbol)
        
        # Crear Treeview
        columnas = [
            "Identificador", "Categoría", "Tipo de Dato", "Ámbito",
            "Dirección", "Línea", "Valor", "Estado", "Estructura", "Referencias"
        ]
        
        tabla = ttk.Treeview(ventana_tabla, columns=columnas, show="headings")
        
        # Configurar columnas
        for col in columnas:
            tabla.heading(col, text=col)
            tabla.column(col, width=120, anchor="center")
        
        # Insertar datos
        if not simbolos:
            tk.Label(ventana_tabla, text="No se encontraron símbolos", fg="red").pack()
        else:
            for simbolo in simbolos:
                valores = [simbolo.get(col, "") for col in columnas]
                tabla.insert("", "end", values=valores)
            
            # Configurar scrollbars
            scroll_y = ttk.Scrollbar(ventana_tabla, orient="vertical", command=tabla.yview)
            scroll_x = ttk.Scrollbar(ventana_tabla, orient="horizontal", command=tabla.xview)
            tabla.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
            
            # Layout
            tabla.grid(row=0, column=0, sticky="nsew")
            scroll_y.grid(row=0, column=1, sticky="ns")
            scroll_x.grid(row=1, column=0, sticky="ew")
            ventana_tabla.grid_rowconfigure(0, weight=1)
            ventana_tabla.grid_columnconfigure(0, weight=1)
    
    except UnexpectedInput as e:
        messagebox.showerror("Error de análisis", f"Error sintáctico: {e}")
    except Exception as e:
        messagebox.showerror("Error inesperado", f"Ocurrió un error: {str(e)}")


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

# Configurar estilos de texto
salida_texto.tag_configure("success", foreground="green")
salida_texto.tag_configure("info", foreground="blue")
salida_texto.tag_configure("error", foreground="red")

ventana.mainloop()


