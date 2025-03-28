from lark import Lark, UnexpectedInput
import tkinter as tk
from tkinter import ttk, scrolledtext, Toplevel,  messagebox
from lark import Lark, UnexpectedInput, Tree, Token
import pickle



# Cargar la gramática desde el archivo
try:
    with open("polux.txt", "r") as file:
        grammar = file.read()
    parser = Lark(grammar, parser="lalr", propagate_positions=True)
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

        # Si no existe, agregarlo como nuevo símbolo
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

    def incrementar_referencia(self, identificador):
        """Incrementa el contador de referencias de un símbolo por su identificador"""
        for simbolo in self.simbolos:
            if simbolo["Identificador"] == identificador:
                simbolo["Referencias"] += 1
                print(f"Referencia incrementada para: {identificador}, Total: {simbolo['Referencias']}")
                return
        # Si no está en memoria principal, buscar en el archivo secundario
        try:
            with open(self.archivo_secundario, "rb") as f:
                simbolos_secundarios = []
                encontrado = False
                while True:
                    simbolo = pickle.load(f)
                    if simbolo["Identificador"] == identificador:
                        simbolo["Referencias"] += 1
                        encontrado = True
                    simbolos_secundarios.append(simbolo)
        except (EOFError, FileNotFoundError):
            pass  # Fin del archivo o archivo no encontrado

        # Reescribir el archivo secundario con los cambios
        if encontrado:
            with open(self.archivo_secundario, "wb") as f:
                for simbolo in simbolos_secundarios:
                    pickle.dump(simbolo, f)
            print(f"Referencia incrementada para: {identificador} en archivo secundario")

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
    # Inicializar la tabla de símbolos global
    tabla_simbolos = TablaSimbolos()
    simbolos = []
    variables_globales = set()

    def get_identifier(node):
        """Obtiene el identificador completo"""
        if isinstance(node, Token):
            return node.value
        return ''.join(get_identifier(child) for child in node.children)

    def get_line(node):
        """Obtiene la línea de declaración del nodo"""
        if hasattr(node, 'meta') and hasattr(node.meta, 'line'):
            return node.meta.line
        return 'N/A'

    def determinar_tipo(node):
        """Determina el tipo de dato basado en el nodo"""
        if isinstance(node, Token):
            # Manejo de tokens
            if node.type in ('integer', 'DIGIT'):
                return 'int'
            elif node.type == 'float':
                return 'float'
            elif node.type == 'STRING_LITERAL':
                return 'string'
            elif node.type in ('booleano', 'True', 'False'):
                return 'bool'
            elif node.type == 'IDENTIFIER':
                return 'desconocido'  # Puede ser una variable o un tipo no definido aún
        elif isinstance(node, Tree):
            # Manejo de subárboles
            if node.data == 'integer':
                return 'int'
            elif node.data == 'float':
                return 'float'
            elif node.data == 'booleano':
                return 'bool'
            elif node.data == 'string_literal':
                return 'string'
            elif node.data == 'array_literal':
                return 'array'
            elif node.data == 'struct_type':
                return 'struct'
            elif node.data == 'type':
                return get_identifier(node.children[0])  # Extrae el tipo explícito
            elif node.data == 'expression':
                # Intenta determinar el tipo de la expresión
                if len(node.children) == 1:
                    return determinar_tipo(node.children[0])
        return 'desconocido'

    for node in tree.iter_subtrees():
        current_line = get_line(node)
        print(f"Procesando nodo: {node.data}, Línea: {current_line}")
        if node.data == "variable_declaration":
            tipo = determinar_tipo(node.children[1]) if len(node.children) > 1 else "desconocido"
            print(f"Tipo de dato detectado: {tipo}")

        # Variables globales
        if node.data == "variable_declaration":
            identificador = get_identifier(node.children[0])
            tipo = determinar_tipo(node.children[1]) if len(node.children) > 1 else "desconocido"
            valor = get_identifier(node.children[1]) if len(node.children) > 1 else "N/A"
            # Incrementar referencia al acceder al símbolo
            tabla_simbolos.incrementar_referencia(identificador)
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

        elif node.data == "constant_declaration":
            print(f"Determinando tipo para constante: {node}")
            identificador = get_identifier(node.children[0])
            tipo = determinar_tipo(node.children[1]) if len(node.children) > 1 else "desconocido"
            valor = get_identifier(node.children[1]) if len(node.children) > 1 else "N/A"
            simbolos.append({
                "Identificador": identificador,
                "Categoría": "Constante",
                "Tipo de Dato": tipo,
                "Ámbito": ambito,
                "Dirección": f"0x{abs(hash(f'{identificador}{ambito}')):X}",
                "Línea": current_line,
                "Valor": valor,
                "Estado": "Inicializado" if valor != "N/A" else "Declarado",
                "Estructura": "Simple",
                "Referencias": 0
            })

        elif node.data == "array_literal":
            identificador = get_identifier(node.children[0])
            tipo = determinar_tipo(node.children[1]) if len(node.children) > 1 else "desconocido"
            valor = get_identifier(node.children[1]) if len(node.children) > 1 else "N/A"
            tabla_simbolos.incrementar_referencia(identificador)
            simbolos.append({
                "Identificador": identificador,
                "Categoría": "Arreglo",
                "Tipo de Dato": "array",
                "Ámbito": ambito,
                "Línea": current_line,
                "Estado": "Inicializado" if valor != "N/A" else "Declarado",
                "Estructura": "Simple",
                "Referencias": 0
            })

        

        # Funciones
        elif node.data == "function_declaration":
            if len(node.children) < 2:
                continue

            identificador = get_identifier(node.children[0])
            params = []

            current_line = get_line(node)

            # Procesar parámetros
            if len(node.children) > 1 and hasattr(node.children[1], 'data') and node.children[1].data == 'parameter_list':
                for param in node.children[1].find_data('parameter'):
                    param_id = get_identifier(param.children[0])
                    param_type = determinar_tipo(param.children[1]) if len(param.children) > 1 else 'desconocido'
                    params.append(f"{param_id}: {param_type}")
                    tabla_simbolos.incrementar_referencia(identificador)
                    simbolos.append({
                        "Identificador": param_id,
                        "Categoría": "Parámetro",
                        "Tipo de Dato": param_type,
                        "Ámbito": identificador,
                        "Dirección": f"0x{abs(hash(f'{param_id}{identificador}')):X}",
                        "Línea": get_line(param),
                        "Valor": "N/A",
                        "Estado": "Declarado",
                        "Estructura": "Simple",
                        "Referencias": 0
                    })

            simbolos.append({
                "Identificador": identificador,
                "Categoría": "Función",
                "Tipo de Dato": f"Función({', '.join(params)})",
                "Ámbito": ambito,
                "Dirección": f"0x{abs(hash(identificador)):X}",
                "Línea": current_line,
                "Valor": f"Parámetros: {len(params)}",
                "Estado": "Definido",
                "Estructura": "Compleja",
                "Referencias": 0
            })

            # Procesar cuerpo de la función
            if len(node.children) > 2:
                cuerpo = node.children[2]
                if cuerpo.data == "block":
                    extraer_simbolos(cuerpo, identificador)

        # Clases
        elif node.data == "class_declaration":
            if len(node.children) < 1:
                continue

            identificador = get_identifier(node.children[0])
            tabla_simbolos.incrementar_referencia(identificador)
            current_line = get_line(node)

            simbolos.append({
                "Identificador": identificador,
                "Categoría": "Clase",
                "Tipo de Dato": "class",
                "Ámbito": ambito,
                "Dirección": f"0x{abs(hash(identificador)):X}",
                "Línea": current_line,
                "Valor": "N/A",
                "Estado": "Definido",
                "Estructura": "Compleja",
                "Referencias": 0
            })

            # Procesar cuerpo de la clase
            if len(node.children) > 1:
                cuerpo = node.children[1]
                if cuerpo.data == "class_body":
                    for elem in cuerpo.children:
                        if elem.data == "variable_declaration":
                            attr_id = get_identifier(elem.children[0])
                            attr_type = determinar_tipo(elem.children[1]) if len(elem.children) > 1 else 'desconocido'

                            simbolos.append({
                                "Identificador": attr_id,
                                "Categoría": "Atributo",
                                "Tipo de Dato": attr_type,
                                "Ámbito": identificador,
                                "Dirección": f"0x{abs(hash(f'{attr_id}{identificador}')):X}",
                                "Línea": get_line(elem),
                                "Valor": "N/A",
                                "Estado": "Declarado",
                                "Estructura": "Simple",
                                "Referencias": 0
                            })
                        elif elem.data == "method_declaration":
                            extraer_simbolos(elem, identificador)

        # Asignaciones
        elif node.data == "assignment_expression":
            if len(node.children) < 2:
                continue

            identificador = get_identifier(node.children[0])
            valor = get_identifier(node.children[1])
            tipo = determinar_tipo(node.children[1])
            tabla_simbolos.incrementar_referencia(identificador)
            simbolos.append({
                "Identificador": identificador,
                "Categoría": "Variable",
                "Tipo de Dato": tipo,
                "Ámbito": ambito,
                "Dirección": f"0x{abs(hash(f'{identificador}{ambito}')):X}",
                "Línea": current_line,
                "Valor": valor,
                "Estado": "Asignado",
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
        ventana_tabla.configure(bg="white")  # Fondo blanco

        # Obtener el código actual
        codigo = entrada_texto.get("1.0", tk.END).strip()
        if not codigo:
            tk.Label(ventana_tabla, text="No hay código para analizar", fg="red", bg="white", font=("Times New Roman", 12, "bold")).pack(pady=10)
            return

        # Parsear y extraer símbolos
        arbol = parser.parse(codigo)
        simbolos = extraer_simbolos(arbol)

        # Crear Treeview
        columnas = [
            "Identificador", "Categoría", "Tipo de Dato", "Ámbito",
            "Dirección", "Línea", "Valor", "Estado", "Estructura", "Referencias"
        ]

        style = ttk.Style()
        style.configure("Treeview", font=("Consolas", 10), background="white", foreground="black", rowheight=25, fieldbackground="white")
        style.configure("Treeview.Heading", font=("Times New Roman", 12, "bold"), background="white", foreground="#1F2833")  # Azul oscuro
        style.map("Treeview.Heading", background=[("active", "#E67E22")])

        tabla = ttk.Treeview(ventana_tabla, columns=columnas, show="headings", style="Treeview")

        # Configurar columnas
        for col in columnas:
            tabla.heading(col, text=col)
            tabla.column(col, width=120, anchor="center")

        # Insertar datos
        if not simbolos:
            tk.Label(ventana_tabla, text="No se encontraron símbolos", fg="red", bg="white", font=("Times New Roman", 12, "bold")).pack(pady=10)
        else:
            for simbolo in simbolos:
                valores = [simbolo.get(col, "") for col in columnas]
                tabla.insert("", "end", values=valores)

            # Configurar scrollbars
            scroll_y = ttk.Scrollbar(ventana_tabla, orient="vertical", command=tabla.yview)
            scroll_x = ttk.Scrollbar(ventana_tabla, orient="horizontal", command=tabla.xview)
            tabla.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

            # Layout
            tabla.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            scroll_y.grid(row=0, column=1, sticky="ns")
            scroll_x.grid(row=1, column=0, sticky="ew", padx=10)
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

style = ttk.Style()
style.configure("TButton", font=("Times New Roman", 12, "bold italic"), padding=8, relief="flat")
style.map("TButton", background=[("active", "#E67E22"), ("!disabled", "#D35400")], foreground=[("active", "white"), ("!disabled", "#447091")])
style.configure("TLabel", font=("Times New Roman", 12, "bold italic"), background="#447091", foreground="white")
style.configure("TFrame", background="#447091")

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


