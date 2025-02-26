import tkinter as tk
from tkinter import scrolledtext, messagebox
from lark import Lark
from lark.exceptions import UnexpectedInput

# Cargar la gramática desde el archivo EBNF
try:
    with open("polux.txt", "r") as file:
        grammar = file.read()
    parser = Lark(grammar, parser="lalr")
    print("Gramática válida")
except Exception as e:
    print(f"Error al cargar la gramática: {e}")
    exit(1)


# Función para realizar el análisis léxico
def analizador_lexico(codigo):
    try:
        # Parsear la sentencia
        parser.parse(codigo)
        print("Parseo correcto")
        
        # Obtener los tokens
        tokens = list(parser.lex(codigo))
        return tokens, None  # Devuelve los tokens y ningún error
    except UnexpectedInput as error:
        # Capturar errores léxicos
        error_msg = f"Error léxico en línea {error.line}, columna {error.column}: {error}"
        return None, error_msg  # Devuelve ningún token y el mensaje de error


# Función para manejar el análisis y mostrar resultados
def analizar():
    # Obtener el código del área de texto
    codigo = entrada_texto.get("1.0", tk.END).strip()
    
    # Realizar el análisis léxico
    tokens, error = analizador_lexico(codigo)
    
    # Limpiar áreas de texto
    salida_texto.delete("1.0", tk.END)
    tabla_simbolos_texto.delete("1.0", tk.END)
    
    if error:
        # Mostrar error en la interfaz
        salida_texto.insert(tk.END, f"Error:\n{error}")
    else:
        # Mostrar tokens en la interfaz
        salida_texto.insert(tk.END, "Tokens encontrados:\n")
        for token in tokens:
            salida_texto.insert(tk.END, f"Token: {token.value} \tCategoría: {token.type}\n")
        
        # Crear y mostrar la tabla de símbolos
        tabla_simbolos = {}
        for token in tokens:
            if token.type not in tabla_simbolos:
                tabla_simbolos[token.type] = []
            tabla_simbolos[token.type].append(token.value)
        
        tabla_simbolos_texto.insert(tk.END, "Tabla de símbolos:\n")
        for tipo, valores in tabla_simbolos.items():
            tabla_simbolos_texto.insert(tk.END, f"{tipo}:\n")
            for valor in valores:
                tabla_simbolos_texto.insert(tk.END, f"  - {valor}\n")


# Crear la ventana principal
ventana = tk.Tk()
ventana.title("Analizador Léxico")
ventana.geometry("800x600")

# Área de texto para ingresar el código fuente
etiqueta_entrada = tk.Label(ventana, text="Ingrese el código fuente:")
etiqueta_entrada.pack(pady=5)

entrada_texto = scrolledtext.ScrolledText(ventana, width=100, height=10)
entrada_texto.pack(pady=5)

# Botón para iniciar el análisis léxico
boton_analizar = tk.Button(ventana, text="Analizar", command=analizar)
boton_analizar.pack(pady=5)

# Área de texto para mostrar los resultados del análisis
etiqueta_salida = tk.Label(ventana, text="Resultados del análisis léxico:")
etiqueta_salida.pack(pady=5)

salida_texto = scrolledtext.ScrolledText(ventana, width=100, height=10)
salida_texto.pack(pady=5)

# Área de texto para mostrar la tabla de símbolos
etiqueta_tabla = tk.Label(ventana, text="Tabla de símbolos:")
etiqueta_tabla.pack(pady=5)

tabla_simbolos_texto = scrolledtext.ScrolledText(ventana, width=100, height=10)
tabla_simbolos_texto.pack(pady=5)

# Iniciar el bucle principal de la interfaz gráfica
ventana.mainloop()
