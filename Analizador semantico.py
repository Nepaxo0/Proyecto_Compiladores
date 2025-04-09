import tkinter as tk
from tkinter import ttk, scrolledtext, Toplevel,  messagebox
from lark import Lark, UnexpectedInput, Tree, Token, Visitor
import pickle

try:
    with open("polux.txt", "r") as file:
        grammar = file.read()
    parser = Lark(grammar, parser="lalr", propagate_positions=True)
    print("Gramática cargada correctamente.")
except Exception as e:
    print(f"Error al cargar la gramática: {e}")
    exit(1)

class SymbolEntry:
    def __init__(self, name, kind, sym_type, scope, line, initialized=False, value=None, is_constant=False, is_mutable=True):
        # Campos Comunes
        self.name = name              # Nombre del identificador
        self.kind = kind              # Categoría: 'variable', 'constante', 'funcion', 'parametro', 'clase', 'tipo', 'atributo', 'metodo'
        self.sym_type = sym_type          # Tipo de dato (string, o un objeto Type más complejo)
        self.scope = scope            # Referencia al Scope donde se declaró
        self.line = line              # Línea de declaración
        self.initialized = initialized    # Estado de inicialización
        self.references = 0           # Contador de usos

        # Campos Específicos para Variables/Constantes
        self.memory_size = None       # Tamaño en memoria (puede calcularse después)
        self.relative_address = None  # Dirección relativa (puede calcularse después)
        self.value = value            # Valor (si es constante o inicializado)
        self.is_constant = is_constant    # Es constante?
        self.is_mutable = not is_constant # Modificabilidad

        # Campos Específicos para Funciones/Procedimientos
        self.signature = None         # Firma (ej: "func(int, string): bool")
        self.parameters = []          # Lista de SymbolEntry para parámetros
        self.return_type = None       # Tipo de retorno (string o Type)
        self.local_symbol_table = None # Referencia a la tabla de símbolos local (Scope)
        self.is_defined = False       # Estado de implementación (declarada vs definida)

        # Campos para Tipos Definidos por el Usuario (Clases/Structs)
        self.internal_structure = {} # Descripción de componentes (atributos)
        self.associated_methods = {} # Métodos asociados
        self.inheritance = None       # Jerarquía de herencia
        self.restrictions = []        # Restricciones específicas

    def __str__(self):
        # Representación básica para la tabla
        return (f"Name: {self.name}, Kind: {self.kind}, Type: {self.sym_type}, Scope: {self.scope.name}, "
                f"Line: {self.line}, Init: {self.initialized}, Refs: {self.references}, "
                f"Value: {self.value if self.value is not None else 'N/A'}, Const: {self.is_constant}")

class Scope:
    def __init__(self, name, level, parent=None):
        self.name = name              # Nombre del ámbito (e.g., "global", "func_main", "class_MyClass")
        self.level = level            # Nivel de anidamiento
        self.parent = parent          # Ámbito padre (None para global)
        self.symbols = {}             # Diccionario de símbolos en este ámbito {name: SymbolEntry}
        self.children_scopes = []     # Ámbitos hijos

    def add_symbol(self, symbol_entry):
        """Agrega un símbolo a este ámbito, verificando duplicados."""
        if symbol_entry.name in self.symbols:
            # Error: Redeclaración en el mismo ámbito
            return False, f"Error: Identificador '{symbol_entry.name}' ya declarado en el ámbito '{self.name}' (Línea: {self.symbols[symbol_entry.name].line})."
        self.symbols[symbol_entry.name] = symbol_entry
        symbol_entry.scope = self # Asegurar que el símbolo conoce su ámbito
        return True, None

    def lookup(self, name, check_parents=True):
        """Busca un símbolo por nombre en este ámbito y opcionalmente en los padres."""
        if name in self.symbols:
            return self.symbols[name]
        if check_parents and self.parent:
            return self.parent.lookup(name, check_parents=True)
        return None # No encontrado

    def __str__(self):
        return f"Scope({self.name}, Level: {self.level}, Parent: {self.parent.name if self.parent else 'None'})"

class SymbolTableManager:
    def __init__(self):
        self.global_scope = Scope("global", 0)
        self.current_scope = self.global_scope
        self.scopes = {"global": self.global_scope} # Para buscar ámbitos por nombre si es necesario
        self._scope_counter = 0 # Para nombres de ámbitos anónimos

    def push_scope(self, name=None):
        """Entra en un nuevo ámbito."""
        if name is None:
            self._scope_counter += 1
            name = f"block_{self._scope_counter}"
        elif name in self.scopes: # Evitar nombres de ámbito duplicados al mismo nivel si son nombrados (funciones, clases)
             # Podría ser un error o necesitar un manejo más complejo si se permiten sobrecargas/sombras de funciones
             # Por ahora, simplemente añadimos un sufijo para diferenciar, pero lo ideal sería validar esto.
             print(f"Advertencia: Ámbito con nombre '{name}' ya existe. Creando uno nuevo.")
             name = f"{name}_{self._scope_counter}"
             self._scope_counter += 1


        new_scope = Scope(name, self.current_scope.level + 1, parent=self.current_scope)
        self.current_scope.children_scopes.append(new_scope)
        self.current_scope = new_scope
        self.scopes[name] = new_scope
        print(f"Entering Scope: {self.current_scope.name} (Level: {self.current_scope.level})") # Debug
        return self.current_scope

    def pop_scope(self):
        """Sale del ámbito actual."""
        if self.current_scope.parent:
            print(f"Exiting Scope: {self.current_scope.name}") # Debug
            self.current_scope = self.current_scope.parent
        else:
            print("Warning: Attempting to pop the global scope.") # No debería ocurrir

    def add_symbol(self, symbol_entry):
        """Agrega un símbolo al ámbito actual."""
        return self.current_scope.add_symbol(symbol_entry)

    def lookup(self, name):
        """Busca un símbolo empezando desde el ámbito actual hacia arriba."""
        return self.current_scope.lookup(name, check_parents=True)

    def get_all_symbols(self):
        """Recorre todos los ámbitos y recopila todos los símbolos."""
        all_symbols = []
        scopes_to_visit = [self.global_scope]
        visited_scopes = set()

        while scopes_to_visit:
            scope = scopes_to_visit.pop(0)
            if scope in visited_scopes:
                continue
            visited_scopes.add(scope)
            all_symbols.extend(scope.symbols.values())
            scopes_to_visit.extend(scope.children_scopes)
        return all_symbols

    def reset(self):
        """Reinicia la tabla de símbolos para un nuevo análisis."""
        self.global_scope = Scope("global", 0)
        self.current_scope = self.global_scope
        self.scopes = {"global": self.global_scope}
        self._scope_counter = 0

# (Añadir esta clase en Analizador sintactico.py)
from lark import Visitor, Token, Tree

class SemanticAnalyzer(Visitor):
    def __init__(self):
        self.symbol_table = SymbolTableManager()
        self.errors = []
        self.current_function = None # Para verificar retornos

    def add_error(self, message, node):
        """Añade un error semántico con información de línea."""
        line = node.meta.line if hasattr(node, 'meta') else 'N/A'
        column = node.meta.column if hasattr(node, 'meta') else 'N/A'
        self.errors.append(f"Error Semántico (Línea {line}, Col {column}): {message}")

    
    def _get_node_text(self, node):
        """Obtiene una representación textual simple de un nodo (Token o Tree)."""
        if isinstance(node, Token):
            return node.value
        elif isinstance(node, Tree):
            # Intenta obtener el valor del primer token hijo si existe
            val = self._get_safe_value(node)
            if val is not None:
                 return val
            # Si no, intenta reconstruir (muy básico)
            # text = ""
            # for child in node.children:
            #     text += self._get_node_text(child) + " " # Recursivo, cuidado con bucles
            # if text:
            #     return text.strip()
            # Fallback: nombre de la regla
            return f"<{node.data}>"
        return str(node) # Último recurso

    def _get_expression_type(self, node):
        """Intenta determinar el tipo de una expresión. Muy simplificado."""
        if isinstance(node, Token):
            if node.type == 'INTEGER' or node.type == 'DIGIT': return 'int'
            # if node.type == 'FLOAT': return 'float' # Asumiendo que tienes FLOAT
            if node.type == 'STRING_LITERAL': return 'string'
            if node.type == 'TRUE' or node.type == 'FALSE' or node.type == 'BOOLEANO': return 'bool'
            if node.type == 'IDENTIFIER':
                symbol = self.symbol_table.lookup(node.value)
                if symbol:
                    # Verificar inicialización antes de usar (excepto en LHS de asignación)
                    # Esta verificación debería hacerse en el contexto del uso
                    # if not symbol.initialized and not self._is_lhs_of_assignment(node):
                    #     self.add_error(f"Variable '{node.value}' usada antes de ser inicializada.", node)
                    return symbol.sym_type # Devolver el tipo del símbolo
                else:
                    self.add_error(f"Identificador '{node.value}' no declarado.", node)
                    return 'error_type' # Tipo especial para indicar error
        elif isinstance(node, Tree):
            # Lógica recursiva para determinar tipo de expresiones compuestas
            if node.data == 'arithmetic_expression':
                left_type = self._get_expression_type(node.children[0])
                right_type = self._get_expression_type(node.children[2])
                op = node.children[1].value if isinstance(node.children[1], Token) else 'op'

                # Comprobación de tipos simple para aritmética
                if left_type == 'int' and right_type == 'int': return 'int'
                # Añadir más reglas (float, etc.)
                elif left_type != 'error_type' and right_type != 'error_type':
                    self.add_error(f"Operación aritmética '{op}' inválida entre tipos '{left_type}' y '{right_type}'.", node)
                return 'error_type'

            elif node.data == 'logical_expression':
                 left_type = self._get_expression_type(node.children[0])
                 right_type = self._get_expression_type(node.children[2])
                 op = node.children[1].value if isinstance(node.children[1], Token) else 'op'
                 # Lógica similar para bool
                 if left_type == 'bool' and right_type == 'bool': return 'bool'
                 elif left_type != 'error_type' and right_type != 'error_type':
                     self.add_error(f"Operación lógica '{op}' inválida entre tipos '{left_type}' y '{right_type}'.", node)
                 return 'error_type'

            elif node.data == 'relational_expression':
                left_type = self._get_expression_type(node.children[0])
                right_type = self._get_expression_type(node.children[2])
                op = node.children[1].value if isinstance(node.children[1], Token) else 'op'
                # Permitir comparaciones entre tipos compatibles (ej. int con int)
                if left_type == right_type and left_type != 'error_type': return 'bool'
                # Añadir reglas para compatibilidad (int/float) si es necesario
                elif left_type != 'error_type' and right_type != 'error_type':
                     self.add_error(f"Comparación '{op}' inválida entre tipos '{left_type}' y '{right_type}'.", node)
                return 'error_type'

            elif node.data == 'assignment_expression':
                 # El tipo de una asignación suele ser el tipo del lado izquierdo,
                 # pero la validación ocurre en visit_assignment_expression
                 return self._get_expression_type(node.children[0])

            elif node.data == 'grouped_expression':
                 return self._get_expression_type(node.children[0]) # Tipo de la expresión interna

            elif node.data == 'identifier': # Si 'identifier' es un nodo Tree en tu gramática
                 return self._get_expression_type(node.children[0])

            elif node.data == 'integer': return 'int'
            elif node.data == 'string_literal': return 'string'
            elif node.data == 'booleano': return 'bool'
            # ... añadir más casos para otros tipos de nodos de expresión ...
            elif node.data == 'method_call':
                 # Buscar la función y devolver su tipo de retorno declarado
                 func_name = self._get_node_text(node.children[0]) # Asumiendo estructura simple
                 symbol = self.symbol_table.lookup(func_name)
                 if symbol and symbol.kind == 'funcion':
                      return symbol.return_type if symbol.return_type else 'void' # O tipo específico si no retorna nada
                 elif symbol:
                      self.add_error(f"'{func_name}' no es una función.", node)
                 # else: el error de no declarado ya se dio al buscar func_name
                 return 'error_type'
            elif node.data == 'array_literal':
                # Determinar tipo del array (podría ser complejo si son mixtos)
                # Asumimos homogéneo por ahora, basado en el primer elemento
                if len(node.children) > 0:
                    element_type = self._get_expression_type(node.children[0])
                    # Verificar que todos los elementos sean del mismo tipo (o compatibles)
                    # ... (lógica de verificación omitida por brevedad) ...
                    return f"array<{element_type}>"
                else:
                    return "array<empty>" # O un tipo genérico
        
        # Si no se puede determinar o es un nodo no esperado en una expresión
        # self.add_error(f"No se puede determinar el tipo para el nodo {node.data if isinstance(node, Tree) else node}.", node)
        return 'desconocido' # O 'error_type' si es claramente un problema
    def _get_safe_value(self, node, expected_type=None):
        """Helper para obtener el valor de un Token o el primer Token de un Tree."""
        if isinstance(node, Token):
            if expected_type is None or node.type == expected_type:
                return node.value
        elif isinstance(node, Tree):
            # Intenta descender al primer Token si el Tree lo envuelve
            if node.children and isinstance(node.children[0], Token):
                 if expected_type is None or node.children[0].type == expected_type:
                     return node.children[0].value
            # Podrías añadir más lógica aquí si la estructura es más compleja
        return None # No se pudo obtener un valor seguro
    
    def _get_token_from_node(self, node, expected_type=None):
         """Helper para obtener el Token, ya sea directamente o desde un Tree."""
         if isinstance(node, Token):
             if expected_type is None or node.type == expected_type:
                 return node
         elif isinstance(node, Tree):
             if node.children and isinstance(node.children[0], Token):
                  if expected_type is None or node.children[0].type == expected_type:
                      return node.children[0]
         return None
    
    def determinar_tipo(self, nodo_valor):
        """
        Función auxiliar para determinar el tipo basado en el nodo del valor.
        Necesitarás adaptarla según los tipos de tokens/nodos que genere tu gramática.
        """
        if isinstance(nodo_valor, Token): # Es un Token?
            if nodo_valor.type == 'NUMBER':
                return 'numero' 
            elif nodo_valor.type == 'STRING':
                return 'texto'
            # Añade más tipos básicos aquí
            else:
                 # Token de tipo desconocido para asignación directa
                 # print(f"Debug: Token desconocido en determinar_tipo: {nodo_valor}") # Debug
                 return "ERROR_TIPO_DESCONOCIDO"

        elif isinstance(nodo_valor, Tree): # Es una instancia de Tree?
            # Ahora es seguro acceder a .data y .children
            if nodo_valor.data == 'expr' and nodo_valor.children:
                 # Llamada recursiva: Asegúrate que el hijo también se maneje
                 return self.determinar_tipo(nodo_valor.children[0])
            else:
                 # Estructura de árbol no manejada o vacía
                 # print(f"Debug: Tree no manejado en determinar_tipo: {nodo_valor.pretty()}") # Debug
                 return "ERROR_TIPO_DESCONOCIDO"
        
        # --- Caso por defecto / Error ---
        # Si nodo_valor no es ni Token ni Tree (podría ser None, u otro tipo inesperado)
        # print(f"Debug: Tipo inesperado en determinar_tipo: {type(nodo_valor)}") # Debug
        return "ERROR_TIPO_DESCONOCIDO"
    
    # --- Visitor Methods ---

    def visit(self, tree):
        """Método principal para iniciar el análisis."""
        self.symbol_table.reset()
        self.errors = []
        self.current_function = None
        super().visit(tree) # Llama a los métodos visit_* correspondientes
        return self.errors

    # Dentro de la clase SemanticAnalyzer, método variable_declaration
    # Dentro de la clase SemanticAnalyzer
    def variable_declaration(self, node):
        """Procesa la declaración de variables, reconstruyendo el nombre desde LETTER/DIGIT."""
        print("\nDEBUG: Entrando a variable_declaration")

        # --- Imprimir info básica del nodo ---
        if isinstance(node, Tree):
            print(f"DEBUG: Nodo recibido: Tree(data='{node.data}') con {len(node.children)} hijos.")
        else:
            print(f"DEBUG: Nodo recibido NO es Tree: {node}")
            self.add_error("Error interno: Se esperaba un nodo Tree para variable_declaration.", node)
            return

        identifier_token_for_meta = None # Guarda el PRIMER token (LETTER) para línea/col
        variable_name = None             # Guarda el nombre completo reconstruido
        identifier_node_index = -1       # Índice del nodo 'identifier' o del token directo

        # --- Búsqueda y Reconstrucción del Identificador ---
        for i, child in enumerate(node.children):
            print(f"  DEBUG: Chequeando hijo {i}: Tipo={type(child)}")

            # CASO PRINCIPAL: El identificador está dentro de un Tree(data='identifier')
            if isinstance(child, Tree) and child.data == 'identifier':
                print(f"    DEBUG: Es Tree(data='identifier'). Reconstruyendo nombre...")
                identifier_node_index = i
                reconstructed_name = ""
                first_token_found = None # Para guardar el primer token de este identificador

                # Iterar sobre los tokens DENTRO del Tree 'identifier' (LETTER, DIGIT, etc.)
                for sub_child in child.children:
                    if isinstance(sub_child, Token):
                        # Guarda el primer token encontrado (debería ser LETTER)
                        if first_token_found is None:
                            first_token_found = sub_child
                            print(f"      DEBUG: Primer token encontrado para meta: Type='{sub_child.type}', Value='{sub_child.value}'")

                        # Concatena el valor del token al nombre
                        reconstructed_name += sub_child.value
                        print(f"      DEBUG: Concatenando: '{sub_child.value}'. Nombre actual: '{reconstructed_name}'")
                    else:
                        # No debería haber otros Trees aquí según la gramática de 'identifier'
                        print(f"      WARN: Se encontró algo inesperado dentro de Tree 'identifier': {type(sub_child)}")

                # Si encontramos tokens dentro y pudimos reconstruir
                if first_token_found:
                    identifier_token_for_meta = first_token_found
                    variable_name = reconstructed_name
                    print(f"    DEBUG: Nombre reconstruido final: '{variable_name}', Token para metadata: {identifier_token_for_meta}")
                    break # Salir del bucle principal (child) porque ya encontramos el identificador
                else:
                    print(f"    WARN: No se encontraron tokens dentro del Tree 'identifier'.")
                    # No hacemos break, podría haber otra forma de declararlo (poco probable)

            # CASO ALTERNATIVO: Si tuvieras un token IDENTIFIER directo (poco probable con tu gramática actual)
            elif isinstance(child, Token) and child.type == 'IDENTIFIER':
                 print(f"    DEBUG: Coincidencia directa encontrada (Token IDENTIFIER): '{child.value}'")
                 identifier_token_for_meta = child
                 variable_name = child.value
                 identifier_node_index = i
                 break

            # --- Verificación post-búsqueda ---
        if variable_name is None or identifier_token_for_meta is None:
            print(f"DEBUG: *** variable_name o identifier_token_for_meta es None DESPUÉS de la búsqueda. Error será añadido. ***")
            # Intenta obtener la línea del nodo padre para el mensaje de error
            error_line = node.meta.line if hasattr(node, 'meta') and hasattr(node.meta, 'line') else 'N/A'
            self.add_error(f"Error interno (Línea ~{error_line}): No se pudo reconstruir el nombre del identificador o encontrar su token inicial.", node)
            return
        else:
            # Imprime info del token meta, pero no accederemos a su .meta para la línea
            print(f"DEBUG: Identificador procesado: Nombre='{variable_name}', Token Meta='{identifier_token_for_meta}' (Type='{identifier_token_for_meta.type}')")

        # --- Obtener metadatos y procesar el resto ---
        # ******** CORRECCIÓN AQUÍ ********
        # Obtener la línea del NODO PADRE ('variable_declaration' -> variable 'node')
        line = 'N/A' # Valor por defecto
        if hasattr(node, 'meta') and hasattr(node.meta, 'line'):
            line = node.meta.line
            print(f"DEBUG: Línea obtenida del nodo 'variable_declaration': {line}")
        else:
            print(f"WARN: No se pudo obtener la línea desde node.meta para la declaración de '{variable_name}'. Se usará 'N/A'.")
            # Como fallback MUY improbable, podrías intentar acceder a .line directamente en el token,
            # pero si .meta no existe, es poco probable que .line sí.
            # if hasattr(identifier_token_for_meta, 'line'):
            #     line = identifier_token_for_meta.line
            #     print(f"DEBUG: Línea obtenida directamente del token meta (fallback): {line}")


        # Lógica para encontrar el nodo de expresión y determinar tipo/inicialización
        variable_type = 'desconocido'
        is_initialized = False
        value = None
        expression_node = None

        # Buscar el nodo de expresión (usando el índice guardado)
        if identifier_node_index != -1 and identifier_node_index + 1 < len(node.children):
            possible_expr_node = node.children[identifier_node_index + 1]
            # Comprobar si el siguiente nodo es el de la expresión
            if isinstance(possible_expr_node, Tree) and possible_expr_node.data == 'expression':
                expression_node = possible_expr_node
                print(f"DEBUG: Nodo de expresión encontrado: {expression_node.data}")
            else:
                 print(f"DEBUG: El nodo siguiente al identificador (índice {identifier_node_index + 1}) no es Tree 'expression'.")
        else:
            print(f"DEBUG: No hay nodo siguiente al identificador o índice inválido ({identifier_node_index}).")


        if expression_node:
            self.visit(expression_node) # Analizar la expresión
            variable_type = self._get_expression_type(expression_node)
            value = self._get_node_text(expression_node) # Obtener texto (puede ser simple)
            is_initialized = True
            print(f"DEBUG: Expresión analizada. Tipo determinado: {variable_type}, Valor Texto: {value}")
        else:
            print(f"DEBUG: No se encontró nodo de expresión para inicialización.")
            # Aquí podrías requerir un tipo explícito si tu lenguaje lo necesita
            # variable_type = 'tipo_requerido_si_no_inicializa'
            is_initialized = False

        # Añadir símbolo a la tabla usando el nombre reconstruido y la línea del primer token
        symbol_entry = SymbolEntry(name=variable_name, kind='variable', sym_type=variable_type,
                                   scope=self.symbol_table.current_scope, line=line,
                                   initialized=is_initialized, value=value) # Añade otros campos necesarios

        success, error_msg = self.symbol_table.add_symbol(symbol_entry)
        if success:
            print(f"DEBUG: Símbolo '{variable_name}' añadido correctamente al scope '{self.symbol_table.current_scope.name}'")
        else:
            print(f"DEBUG: Falló al añadir símbolo '{variable_name}'. Mensaje: {error_msg}")
            self.add_error(error_msg, identifier_token_for_meta) # Reportar error en la línea del identificador

    def constant_declaration(self, node):
        """Procesa la declaración de constantes."""
        cte_token = self._get_token_from_node(node.children[0], 'IDENTIFIER')
        if not cte_token:
            self.add_error("Error interno: No se encontró el token IDENTIFIER en la declaración de constante.", node.children[0])
            return
        const_name = cte_token.value
        line = cte_token.meta.line

        if len(node.children) < 3:
             self.add_error("Declaración de constante incompleta.", node)
             return

        expression_node = node.children[2]
        const_type = self._get_expression_type(expression_node)
        const_value = self._get_node_text(expression_node) # Simplificado

        if const_type == 'error_type':
            self.add_error(f"Error en la expresión de la constante '{const_name}'.", expression_node)
            const_type = 'desconocido'

        symbol = SymbolEntry(name=const_name, kind='constante', sym_type=const_type, scope=self.symbol_table.current_scope, line=line, initialized=True, value=const_value, is_constant=True)

        success, error_msg = self.symbol_table.add_symbol(symbol)
        if not success:
            self.add_error(error_msg, cte_token)

        # Visitar la expresión (aunque sea constante, puede contener errores)
        self.visit(expression_node)


    def assignment_expression(self, node):
        """Procesa asignaciones."""
        target_node = node.children[0]
        value_node = node.children[2] # Asumiendo target assign_op value

        # Visitar primero el lado derecho para obtener su tipo y detectar errores allí
        self.visit(value_node)
        value_type = self._get_expression_type(value_node)

        # Visitar el lado izquierdo DESPUÉS para manejar el lookup y la asignación
        # self.visit(target_node) # ¡Cuidado! Visitar target_node puede causar problemas si es solo un ID

        if isinstance(target_node, Token) and target_node.type == 'IDENTIFIER':
             var_name = target_node.value
             symbol = self.symbol_table.lookup(var_name)

             if not symbol:
                 self.add_error(f"Variable '{var_name}' no declarada.", target_node)
                 return
             if symbol.is_constant:
                 self.add_error(f"No se puede asignar a la constante '{var_name}'.", target_node)
                 return
             if not symbol.is_mutable:
                  self.add_error(f"Variable '{var_name}' es inmutable o de solo lectura.", target_node)
                  return # Asumiendo que tienes esta lógica

             target_type = symbol.sym_type

             # Comprobación de compatibilidad de tipos
             if value_type != 'error_type' and target_type != 'desconocido' and value_type != 'desconocido' and target_type != value_type:
                  # Aquí se necesitaría una lógica más sofisticada para conversiones implícitas permitidas
                  is_compatible = False
                  # Ejemplo: Permitir asignar int a float (si tuvieras float)
                  # if target_type == 'float' and value_type == 'int':
                  #    is_compatible = True

                  if not is_compatible:
                      self.add_error(f"Tipo incompatible: No se puede asignar tipo '{value_type}' a variable '{var_name}' de tipo '{target_type}'.", node)

             # Marcar como inicializada (si no lo estaba ya)
             symbol.initialized = True
             symbol.references += 1 # La asignación también cuenta como referencia

        elif isinstance(target_node, Tree):
             # Manejar asignaciones más complejas (ej: array[index] = value, obj.attribute = value)
             # Esto requiere lógica específica para cada caso
             if target_node.data == 'array_access': # Si tienes una regla así
                  # ... verificar array, índice, tipo ...
                  pass
             elif target_node.data == 'member_access': # Si tienes obj.miembro
                  # ... verificar objeto, miembro, tipo ...
                  pass
             else:
                  self.add_error("Asignación inválida: el lado izquierdo debe ser una variable, elemento de array o miembro.", target_node)
        else:
             self.add_error("Asignación inválida: el lado izquierdo no es un identificador válido.", target_node)


    def identifier(self, node):
         """Verifica el uso de identificadores en expresiones."""
         # Este método se llamará si 'identifier' es un nodo del árbol (no solo un Token)
         # Si 'identifier' es solo un Token, la verificación se hará dentro de _get_expression_type
         # o en el contexto donde se use (ej: method_call).
         # Asumamos que 'identifier' es un Token que se procesa en otros nodos.
         pass # La lógica principal está en lookup y _get_expression_type


    def expression(self, node):
         """Visita nodos de expresión para asegurar que los hijos se visiten."""
         # Llama al visitador genérico para los hijos, lo que activará
         # arithmetic_expression, logical_expression, etc.
         self._visit_children(node)
         # Podrías añadir verificaciones generales de expresión aquí si es necesario


    def arithmetic_expression(self, node):
        """Verifica operaciones aritméticas."""
        self._visit_children(node) # Visita operandos primero
        # La comprobación de tipos se hace en _get_expression_type al evaluar el nodo padre
        # pero podríamos añadirla aquí también por redundancia o especificidad.
        left_type = self._get_expression_type(node.children[0])
        right_type = self._get_expression_type(node.children[2])
        op_node = node.children[1]
        op_token = self._get_token_from_node(op_node) # Intenta obtener el token del operador
        op = op_token.value if op_token else f"<{op_node.data if isinstance(op_node, Tree) else '?'}>"
        op_line_node = op_token if op_token else op_node

        # Ejemplo: División por cero (si es detectable en compilación)
        if op == '/':
            right_operand = node.children[2]
            if isinstance(right_operand, Token) and (right_operand.type == 'INTEGER' or right_operand.type == 'DIGIT'):
                if int(right_operand.value) == 0:
                     self.add_error("Posible división por cero detectada en tiempo de compilación.", right_operand)
            # (Necesitaría evaluación constante más compleja para detectarlo en expresiones)

        # Verificar si el operador es válido para los tipos
        valid_types = ['int'] # Añadir 'float' si existe
        if left_type not in valid_types or right_type not in valid_types:
             if left_type != 'error_type' and right_type != 'error_type': # Evitar errores cascada
                 self.add_error(f"Operador aritmético '{op}' no se puede aplicar a tipos '{left_type}' y '{right_type}'.", op_node)


    def relational_expression(self, node):
         """Verifica operaciones relacionales."""
         self._visit_children(node)
         left_type = self._get_expression_type(node.children[0])
         right_type = self._get_expression_type(node.children[2])
         op_node = node.children[1]
         op_token = self._get_token_from_node(op_node)
         op = op_token.value if op_token else f"<{op_node.data if isinstance(op_node, Tree) else '?'}>"
         op_line_node = op_token if op_token else op_node

         # Los tipos deben ser comparables
         if left_type != right_type and (left_type != 'error_type' and right_type != 'error_type'):
              # Permitir comparaciones int/float si es necesario
              # if not ((left_type == 'int' and right_type == 'float') or \
              #         (left_type == 'float' and right_type == 'int')):
                   self.add_error(f"No se pueden comparar tipos incompatibles: '{left_type}' {op} '{right_type}'.", op_node)


    def logical_expression(self, node):
         """Verifica operaciones lógicas."""
         self._visit_children(node)
         left_type = self._get_expression_type(node.children[0])
         right_type = self._get_expression_type(node.children[2])
         op_node = node.children[1]
         op_token = self._get_token_from_node(op_node)
         op = op_token.value if op_token else f"<{op_node.data if isinstance(op_node, Tree) else '?'}>"
         op_line_node = op_token if op_token else op_node

         if left_type != 'bool' or right_type != 'bool':
               if left_type != 'error_type' and right_type != 'error_type':
                  self.add_error(f"Operador lógico '{op}' requiere operandos booleanos, pero se encontraron '{left_type}' y '{right_type}'.", op_node)
         # Manejar NOT si tiene una estructura diferente


    def if_statement(self, node):
        """Verifica sentencias IF."""
        condition_node = node.children[0] # Asumiendo if (expression) || block || else?
        self.visit(condition_node)
        condition_type = self._get_expression_type(condition_node)

        if condition_type not in ['bool', 'error_type', 'desconocido']: # Permitir desconocido para no dar error doble
             self.add_error(f"La condición del 'if' debe ser booleana, pero se encontró tipo '{condition_type}'.", condition_node)

        # Visitar los bloques
        self.visit(node.children[1]) # Bloque THEN
        if len(node.children) > 2: # Si hay ELSE
             self.visit(node.children[2]) # Bloque ELSE (o nodo else_clause)

    def while_loop(self, node):
        """Verifica bucles WHILE."""
        condition_node = node.children[0] # Asumiendo while (expression) || block ||
        self.visit(condition_node)
        condition_type = self._get_expression_type(condition_node)

        if condition_type not in ['bool', 'error_type', 'desconocido']:
             self.add_error(f"La condición del 'while' debe ser booleana, pero se encontró tipo '{condition_type}'.", condition_node)

        # Visitar el bloque del bucle
        self.visit(node.children[1]) # Bloque del Bucle

    # --- Funciones ---

    def function_declaration(self, node):
        """Procesa la declaración de funciones."""
        # Estructura asumida: DO "function" identifier "(" parameter_list? ")" "||" statement_block "||"
        func_token = None
        idx = 0
        for i, child in enumerate(node.children):
             # Buscar el token 'function' (o el nodo DO si es lo primero)
             # y tomar el siguiente token/nodo como el identificador
             if isinstance(child, Token) and child.value == 'function':
                  if i + 1 < len(node.children):
                      func_token_node = node.children[i+1]
                      func_token = self._get_token_from_node(func_token_node, 'IDENTIFIER')
                      idx = i+1 # Guardar índice para referencia posterior
                      break
             # Alternativa si el primer nodo es DO
             elif isinstance(child, Token) and child.value == 'DO' and i + 2 < len(node.children):
                 # Asumiendo DO 'function' IDENTIFIER ...
                 func_token_node = node.children[i+2]
                 func_token = self._get_token_from_node(func_token_node, 'IDENTIFIER')
                 idx = i+2
                 break

        if not func_token:
             self.add_error("Error interno: No se pudo encontrar el nombre de la función en la declaración.", node)
             return
        func_name = func_token.value
        line = func_token.meta.line

        # TODO: Determinar tipo de retorno (necesita sintaxis en la gramática, ej: ... ) -> type ||)
        return_type = 'void' # Asumir void si no se especifica

        param_list_node = None
        statement_block_node = None

        # Encontrar los nodos correctos (esto depende MUCHO de tu AST exacto)
        for child in node.children:
            if isinstance(child, Tree):
                if child.data == 'parameter_list':
                    param_list_node = child
                elif child.data == 'statement_block':
                    statement_block_node = child

        # Crear entrada de símbolo para la función ANTES de entrar al nuevo ámbito
        function_symbol = SymbolEntry(name=func_name, kind='funcion', sym_type=f"function(...)->{return_type}", scope=self.symbol_table.current_scope, line=line)
        function_symbol.return_type = return_type
        function_symbol.is_defined = True # Marcamos como definida porque tenemos el bloque

        # Procesar parámetros
        param_symbols = []
        param_types_for_sig = []
        if param_list_node:
            for i, param_node in enumerate(param_list_node.children): # Asumiendo que los hijos son los parámetros
                if isinstance(param_node, Tree) and param_node.data == 'parameter':
                    # Asumiendo: parameter: identifier (':' type)?
                    param_name_token = param_node.children[0]
                    param_name = param_name_token.value
                    param_line = param_name_token.meta.line
                    param_type = 'desconocido' # Tipo por defecto o inferido
                    if len(param_node.children) > 1:
                         # TODO: Extraer tipo explícito si existe en tu gramática
                         # param_type = self._get_node_text(param_node.children[1]) # Ajustar índice
                         pass

                    param_entry = SymbolEntry(name=param_name, kind='parametro', sym_type=param_type, scope=None, line=param_line, initialized=True) # Parámetros se consideran inicializados
                    param_symbols.append(param_entry)
                    param_types_for_sig.append(param_type)
                elif isinstance(param_node, Token) and param_node.type == 'IDENTIFIER':
                     # Caso simple: solo identificador como parámetro
                     param_name = param_node.value
                     param_line = param_node.meta.line
                     param_type = 'desconocido'
                     param_entry = SymbolEntry(name=param_name, kind='parametro', sym_type=param_type, scope=None, line=param_line, initialized=True)
                     param_symbols.append(param_entry)
                     param_types_for_sig.append(param_type)


        function_symbol.parameters = param_symbols
        function_symbol.signature = f"({', '.join(param_types_for_sig)}) -> {return_type}"
        function_symbol.sym_type = f"function{function_symbol.signature}" # Actualizar tipo con firma

        # Añadir la función al ámbito actual (antes de entrar al nuevo)
        success, error_msg = self.symbol_table.add_symbol(function_symbol)
        if not success:
            # Error de redeclaración de función (o variable con mismo nombre)
            self.add_error(error_msg, func_token)
            # Podríamos no continuar con el cuerpo si hay error de declaración
            # return


        # --- Entrar al Ámbito de la Función ---
        self.symbol_table.push_scope(func_name)
        previous_function = self.current_function
        self.current_function = function_symbol # Guardar referencia a la función actual
        function_symbol.local_symbol_table = self.symbol_table.current_scope # Vincular tabla local

        # Añadir parámetros al nuevo ámbito local
        for p_sym in param_symbols:
            success_p, error_msg_p = self.symbol_table.add_symbol(p_sym)
            if not success_p:
                 # Este error (redeclaración de parámetro) es menos probable si los nombres son únicos en la lista
                 self.add_error(error_msg_p, func_token) # Reportar en la línea de la función


        # Visitar el cuerpo de la función
        if statement_block_node:
             self.visit(statement_block_node) # Analizar el cuerpo
        else:
             self.add_error(f"Función '{func_name}' declarada pero no tiene cuerpo.", func_token)


        # --- Salir del Ámbito de la Función ---
        self.symbol_table.pop_scope()
        self.current_function = previous_function # Restaurar función anterior (si estábamos anidados)

        # TODO: Verificación de retorno (requiere análisis de flujo o al menos buscar 'return')
        # Necesitaría un flag 'has_return_statement' que se active al visitar un 'return'
        # if function_symbol.return_type != 'void' and not hasattr(function_symbol, '_has_return'):
        #    self.add_error(f"Función '{func_name}' debe retornar un valor de tipo '{function_symbol.return_type}', pero no se encontró sentencia 'return'.", func_token)


    def method_call(self, node):
        """Verifica llamadas a funciones/métodos."""
        # Asumiendo: identifier "(" argument_list? ")"  O obj.method(...)
        # Simplificado a: identifier "(" argument_list? ")"
        func_token = self._get_token_from_node(node.children[0], 'IDENTIFIER')
        if not func_token:
             # Podría ser una llamada más compleja como obj.method()
             # Necesitarías manejar 'member_access' aquí o en _get_expression_type
             # Por ahora, asumimos llamada simple
             self.add_error("Error interno: No se encontró el identificador de la función en la llamada.", node.children[0])
             # Visitar argumentos igualmente para detectar errores dentro de ellos
             if len(node.children) > 1 and isinstance(node.children[1], Tree) and node.children[1].data == 'argument_list':
                  self.visit(node.children[1])
             return
        func_name = func_token.value
        line = func_token.meta.line

        symbol = self.symbol_table.lookup(func_name)

        if not symbol:
             self.add_error(f"Función o método '{func_name}' no declarado.", func_name_token)
             # Visitar argumentos igualmente para detectar errores dentro de ellos
             if len(node.children) > 1 and isinstance(node.children[1], Tree) and node.children[1].data == 'argument_list':
                  self.visit(node.children[1])
             return

        if symbol.kind not in ['funcion', 'metodo']: # Asumiendo que tienes 'metodo'
             self.add_error(f"'{func_name}' no es una función o método, es de tipo '{symbol.kind}'.", func_name_token)
             # Visitar argumentos
             if len(node.children) > 1 and isinstance(node.children[1], Tree) and node.children[1].data == 'argument_list':
                  self.visit(node.children[1])
             return

        symbol.references += 1 # Incrementar referencia

        # Comparar argumentos
        formal_params = symbol.parameters
        actual_args_nodes = []
        if len(node.children) > 1 and isinstance(node.children[1], Tree) and node.children[1].data == 'argument_list':
             actual_args_nodes = node.children[1].children # Los nodos de expresión de los argumentos

        # Verificar número de argumentos
        if len(formal_params) != len(actual_args_nodes):
             self.add_error(f"Llamada a '{func_name}': Se esperaban {len(formal_params)} argumentos, pero se proporcionaron {len(actual_args_nodes)}.", func_name_token)
             # Aún así, visitar los argumentos que sí se pasaron
             for arg_node in actual_args_nodes:
                  self.visit(arg_node)
             return # Salir si el número no coincide para evitar errores de índice

        # Verificar tipos de argumentos
        for i, arg_node in enumerate(actual_args_nodes):
             self.visit(arg_node) # Visitar el argumento para detectar errores internos
             actual_type = self._get_expression_type(arg_node)
             formal_type = formal_params[i].sym_type

             if actual_type != 'error_type' and formal_type != 'desconocido' and actual_type != 'desconocido' and actual_type != formal_type:
                   # Añadir lógica de compatibilidad si es necesario
                   is_compatible = False
                   # ej: if formal_type == 'float' and actual_type == 'int': is_compatible = True

                   if not is_compatible:
                       self.add_error(f"Llamada a '{func_name}': Argumento {i+1} incompatible. Se esperaba tipo '{formal_type}', pero se encontró tipo '{actual_type}'.", arg_node)


    # Añadir más métodos visit_* para class_declaration, control_structure, print_statement, etc.
    # según tu gramática y las validaciones necesarias.

    # Helper para visitar hijos (evita repetición)
    def _visit_children(self, node):
        for child in node.children:
            if isinstance(child, Tree):
                self.visit(child)
            # Podrías querer visitar Tokens específicos si contienen identificadores a verificar
            # elif isinstance(child, Token) and child.type == 'IDENTIFIER':
            #    self.check_identifier_usage(child)


    # --- Ejemplo de Verificación de Uso ---
    def check_identifier_usage(self, token):
         """Llamado cuando se encuentra un IDENTIFIER en un contexto de uso."""
         identifier = token.value
         symbol = self.symbol_table.lookup(identifier)
         if not symbol:
              self.add_error(f"Identificador '{identifier}' no declarado.", token)
         else:
              symbol.references += 1
              # Comprobar inicialización (si no es el lado izquierdo de una asignación)
              # Necesita contexto para saber si es LHS.
              # if not symbol.initialized and not self._is_lhs_of_assignment(token):
              #     self.add_error(f"Variable '{identifier}' usada antes de ser inicializada.", token)

# (Dentro de Analizador sintactico.py)

# ... (importaciones y código anterior) ...

# Instancia global del analizador semántico (o crearla dentro de analizar)
semantic_analyzer = SemanticAnalyzer()
# La tabla de símbolos ahora la maneja el semantic_analyzer internamente
# global tabla_simbolos # Ya no necesitamos la tabla global antigua

# ... (Clase SymbolEntry, Scope, SymbolTableManager, SemanticAnalyzer) ...


# Función para analizar código y mostrar errores en la interfaz
def analizar():
    # Obtener el código fuente del área de texto
    codigo = entrada_texto.get("1.0", tk.END).strip()

    # Configurar el widget de salida
    salida_texto.config(state=tk.NORMAL)
    salida_texto.delete("1.0", tk.END)
    entrada_texto.tag_remove("error", "1.0", tk.END) # Limpiar resaltado de error anterior

    # Verificar si hay código para analizar
    if not codigo:
        salida_texto.insert(tk.END, "Error: No hay código para analizar\n", "error")
        salida_texto.config(state=tk.DISABLED)
        return

    try:
        salida_texto.insert(tk.END, "--- Análisis Sintáctico ---\n", "info")
        arbol = parser.parse(codigo)
        salida_texto.insert(tk.END, "✓ Análisis sintáctico completado con éxito\n", "success")

        # --- DEBUG: Print AST node names ---
        print("\n--- AST Structure (Relevant Nodes) ---")
        def print_node_names(node, indent=""):
            if isinstance(node, Tree):
                print(f"{indent}Node: {node.data}")
                for child in node.children:
                    print_node_names(child, indent + "  ")
            # Optional: print tokens too
            # elif isinstance(node, Token):
            #    print(f"{indent}Token: {node.type} ({node.value})")
        print_node_names(arbol)
        print("------------------------------------\n")
        # --- END DEBUG ---

        salida_texto.insert(tk.END, "--- Análisis Semántico ---\n", "info")
        semantic_errors = semantic_analyzer.visit(arbol) 

        if not semantic_errors:
            salida_texto.insert(tk.END, "✓ Análisis semántico completado con éxito\n", "success")

            # Opcional: Mostrar resumen de la tabla de símbolos semántica
            all_symbols = semantic_analyzer.symbol_table.get_all_symbols()
            salida_texto.insert(tk.END, f"\nSe encontraron {len(all_symbols)} símbolos válidos:\n", "info")
            categorias = {}
            for s in all_symbols:
                categorias[s.kind] = categorias.get(s.kind, 0) + 1
            for cat, cantidad in categorias.items():
                salida_texto.insert(tk.END, f"- {cat}: {cantidad}\n", "info")

        else:
            salida_texto.insert(tk.END, f"✗ Se encontraron {len(semantic_errors)} errores semánticos:\n", "error")
            for error_msg in semantic_errors:
                salida_texto.insert(tk.END, f"- {error_msg}\n", "error")
                # Intenta resaltar la línea del primer error (simple)
                try:
                    line_info = error_msg.split('(Línea ')[1].split(',')[0]
                    if line_info != 'N/A':
                        line_num = int(line_info)
                        entrada_texto.tag_add("error", f"{line_num}.0", f"{line_num}.end")
                        entrada_texto.tag_config("error", background="orange", foreground="black")
                except Exception:
                    pass # No resaltar si no se puede parsear la línea


    except UnexpectedInput as e:
        # Manejar errores sintácticos
        error_msg = f"✗ Error Sintáctico (Línea {e.line}, Col {e.column}):\n"
        # error_msg += f"Contexto: {e.get_context(codigo)}\n" # Puede ser muy largo
        expected = sorted([t for t in e.accepts if not t.startswith('__')]) if hasattr(e, 'accepts') else ['desconocido']
        error_msg += f"Token inesperado: '{e.token}'. Se esperaba: {', '.join(expected[:10])}{'...' if len(expected) > 10 else ''}\n"

        salida_texto.insert(tk.END, "--- Análisis Sintáctico ---\n", "info")
        salida_texto.insert(tk.END, error_msg, "error")

        # Resaltar el error en el código
        try:
            inicio = f"{e.line}.{e.column-1}" # Columna es 1-based
            fin = f"{e.line}.{e.column + len(e.token.value) -1}" if e.token else f"{e.line}.{e.column}"
            entrada_texto.tag_add("error", inicio, fin)
            entrada_texto.tag_config("error", background="red", foreground="white")
        except tk.TclError: # En caso de que los índices no sean válidos
             print(f"Error al resaltar línea {e.line}, col {e.column}")


    except Exception as e:
        # Manejar otros errores inesperados
        salida_texto.insert(tk.END, f"Error inesperado durante el análisis: {str(e)}\n", "error")
        import traceback
        traceback.print_exc() # Imprimir traceback en consola para depuración

    finally:
        # Deshabilitar la edición del widget de salida
        salida_texto.config(state=tk.DISABLED)


# Función para mostrar la tabla de símbolos en una nueva ventana (MODIFICADA)
def mostrar_tabla_simbolos():
    try:
        
        ventana_tabla = Toplevel(ventana)
        ventana_tabla.title("Tabla de Símbolos (Semántica)")
        ventana_tabla.geometry("1400x700") # Más ancha para más columnas
        ventana_tabla.configure(bg="white")

        # Usar los símbolos del último análisis semántico exitoso (si hubo)
        # Idealmente, 'analizar' debería guardar la tabla si no hay errores
        # Por ahora, la obtenemos directamente del analizador
        simbolos = semantic_analyzer.symbol_table.get_all_symbols() # Obtener todos los símbolos de todos los ámbitos

        if not simbolos:
             # Comprobar si hubo errores semánticos que impidieron llenar la tabla
             if semantic_analyzer.errors:
                  tk.Label(ventana_tabla, text="El análisis semántico falló. No se generó la tabla completa.", fg="orange", bg="white", font=("Times New Roman", 12, "bold")).pack(pady=10)
             else: # O si simplemente no había símbolos
                  tk.Label(ventana_tabla, text="No se encontraron símbolos en el código o no se ha analizado.", fg="red", bg="white", font=("Times New Roman", 12, "bold")).pack(pady=10)
             return

        # Definir las columnas basadas en la nueva estructura SymbolEntry
        columnas = [
            "Nombre", "Categoría", "Tipo", "Ámbito", "Nivel Ámbito", "Línea Decl.",
            "Inicializado", "Referencias", "Valor/Firma", "Constante", "Mutable",
            "Tipo Retorno", "#Params", # Añade más según necesites: "Tamaño", "Dirección", etc.
        ]

        style = ttk.Style()
        style.configure("Treeview", font=("Consolas", 10), background="white", foreground="black", rowheight=25, fieldbackground="white")
        style.configure("Treeview.Heading", font=("Times New Roman", 11, "bold"), background="#EAECEE", foreground="#17202A")
        style.map("Treeview.Heading", background=[("active", "#D5D8DC")])

        tabla = ttk.Treeview(ventana_tabla, columns=columnas, show="headings", style="Treeview")

        # Configurar columnas
        for col in columnas:
            tabla.heading(col, text=col)
            tabla.column(col, width=110, anchor="w") # Anchor west para mejor lectura

        tabla.column("Nombre", width=130)
        tabla.column("Tipo", width=150)
        tabla.column("Valor/Firma", width=200)
        tabla.column("Línea Decl.", width=80, anchor="center")
        tabla.column("Referencias", width=80, anchor="center")
        tabla.column("Nivel Ámbito", width=80, anchor="center")

        # Insertar datos desde los objetos SymbolEntry
        for simbolo in simbolos:
            scope_name = simbolo.scope.name if simbolo.scope else 'N/A'
            scope_level = simbolo.scope.level if simbolo.scope else 'N/A'
            valor_firma = simbolo.value if simbolo.kind in ['variable', 'constante'] and simbolo.value is not None else (simbolo.signature if simbolo.kind == 'funcion' else 'N/A')
            ret_type = simbolo.return_type if simbolo.kind == 'funcion' else 'N/A'
            num_params = len(simbolo.parameters) if simbolo.kind == 'funcion' else 'N/A'

            valores = [
                simbolo.name,
                simbolo.kind,
                simbolo.sym_type,
                scope_name,
                scope_level,
                simbolo.line,
                simbolo.initialized,
                simbolo.references,
                str(valor_firma)[:100], # Limitar longitud para visualización
                simbolo.is_constant,
                simbolo.is_mutable,
                ret_type,
                num_params
            ]
            tabla.insert("", "end", values=valores)

        # Scrollbars
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
         messagebox.showerror("Error de Análisis Sintáctico", f"No se puede generar la tabla debido a un error sintáctico previo:\n{e}")
    except Exception as e:
        messagebox.showerror("Error inesperado", f"Ocurrió un error al mostrar la tabla: {str(e)}")
        import traceback
        traceback.print_exc()


# ... (resto de la configuración de la UI: ventana, frame, widgets, mainloop) ...
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

# Asegúrate de reemplazar la llamada a extraer_simbolos y la tabla_simbolos global antigua
# por el uso del semantic_analyzer.

# Ejecutar la aplicación
ventana.mainloop()