import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from lark import Lark
from lark.exceptions import UnexpectedInput

# Cargar la gramática desde el archivo EBNF
try:
    with open("ebnf1.txt", "r") as file:
        grammar = file.read()
    parser = Lark(grammar, parser="lalr")
    print("Gramática válida")
except Exception as e:
    print(f"Error al cargar la gramática: {e}")
    exit(1)

# Función para realizar el análisis léxico
def analizador_lexico(codigo):
    try:
        parser.parse(codigo)
        tokens = list(parser.lex(codigo))
        return tokens, None
    except UnexpectedInput as error:
        return None, f"Error léxico en línea {error.line}, columna {error.column}: {error}"

# Función para manejar el análisis y mostrar resultados
def analizar():
    codigo = entrada_texto.get("1.0", tk.END).strip()
    tokens, error = analizador_lexico(codigo)
    salida_texto.config(state=tk.NORMAL)
    tabla_simbolos_texto.config(state=tk.NORMAL)
    salida_texto.delete("1.0", tk.END)
    tabla_simbolos_texto.delete("1.0", tk.END)
    if error:
        salida_texto.insert(tk.END, f"Error:\n{error}")
    else:
        salida_texto.insert(tk.END, "Tokens encontrados:\n")
        tabla_simbolos = {}
        for token in tokens:
            salida_texto.insert(tk.END, f"Token: {token.value} \tCategoría: {token.type}\n")
            if token.type not in tabla_simbolos:
                tabla_simbolos[token.type] = []
            tabla_simbolos[token.type].append(token.value)
        tabla_simbolos_texto.insert(tk.END, "Tabla de símbolos:\n")
        for tipo, valores in tabla_simbolos.items():
            tabla_simbolos_texto.insert(tk.END, f"{tipo}:\n")
            for valor in valores:
                tabla_simbolos_texto.insert(tk.END, f"  - {valor}\n")
    salida_texto.config(state=tk.DISABLED)
    tabla_simbolos_texto.config(state=tk.DISABLED)

# Crear la ventana principal
ventana = tk.Tk()
ventana.title("Analizador Léxico")
ventana.geometry("900x700")
ventana.configure(bg="#447091")


style = ttk.Style()
style.configure("TButton", font=("Times New Roman", 12, "bold italic"), padding=8, relief="flat")
style.map("TButton",
          background=[("active", "#E67E22"), ("!disabled", "#D35400")],
          foreground=[("active", "white"), ("!disabled", "#447091")])

style.configure("TLabel", font=("Times New Roman", 12, "bold italic"), background="#447091", foreground="white")
style.configure("TFrame", background="#447091")

frame = ttk.Frame(ventana)
frame.pack(padx=20, pady=20, fill="both", expand=True)

etiqueta_entrada = ttk.Label(frame, text="Ingrese el código fuente:")
etiqueta_entrada.pack(anchor="w")

entrada_texto = scrolledtext.ScrolledText(frame, width=90, height=10, font=("Consolas", 10), bg="#ECF0F1", fg="#1F2833")
entrada_texto.pack(pady=5)

boton_analizar = ttk.Button(frame, text="Compilar", command=analizar)
boton_analizar.pack(pady=10)

etiqueta_salida = ttk.Label(frame, text="Resultados del análisis léxico:")
etiqueta_salida.pack(anchor="w")

salida_texto = scrolledtext.ScrolledText(frame, width=90, height=10, font=("Consolas", 10), bg="#ECF0F1", fg="#1F2833", state=tk.DISABLED)
salida_texto.pack(pady=5)

etiqueta_tabla = ttk.Label(frame, text="Tabla de símbolos:")
etiqueta_tabla.pack(anchor="w")

tabla_simbolos_texto = scrolledtext.ScrolledText(frame, width=90, height=10, font=("Consolas", 10), bg="#ECF0F1", fg="#1F2833", state=tk.DISABLED)
tabla_simbolos_texto.pack(pady=5)

ventana.mainloop()
