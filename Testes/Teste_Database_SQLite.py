import sqlite3

def main():
  try:
    # Conectar ao banco de dados
    conn = sqlite3.connect('DB.db')
    cursor = conn.cursor()

    # Criando a tabela vendedores
    try:
      cursor.execute("""
        CREATE TABLE IF NOT EXISTS vendedores (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          nome TEXT NOT NULL,
          email TEXT
        )
      """)
      print("Tabela 'vendedores' criada ou já existe.")
    except sqlite3.Error as e:
      print(f"Erro ao criar a tabela 'vendedores': {e}")

    # Criar a tabela pedidos
    try:
      cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          vendedor_id INTEGER,
          produto TEXT,
          quantidade INTEGER,
          FOREIGN KEY (vendedor_id) REFERENCES vendedores(id)
        )
      """)
      print("Tabela 'pedidos' criada ou já existe.")
    except sqlite3.Error as e:
      print(f"Erro ao criar a tabela 'pedidos': {e}")

    # Inserir dados na tabela vendedores
    try:
      cursor.execute("""
        INSERT INTO vendedores (nome, email) VALUES
          ('Alice', 'alice@mail.com'),
          ('Bruno', 'bruno@mail.com'),
          ('Carla', 'carla@mail.com')
      """)
      conn.commit()
      print("Dados inseridos na tabela 'vendedores'.")
    except sqlite3.IntegrityError as e:
      print(f"Erro de integridade ao inserir dados em 'vendedores': {e}")
    except sqlite3.Error as e:
      print(f"Erro ao inserir dados em 'vendedores': {e}")

    # Inserir dados na tabela pedidos
    try:
      cursor.execute("""
        INSERT INTO pedidos (vendedor_id, produto, quantidade) VALUES
          (1, 'Produto A', 10),
          (2, 'Produto B', 5),
          (3, 'Produto C', 7)
      """)
      conn.commit()
      print("Dados inseridos na tabela 'pedidos'.")
    except sqlite3.IntegrityError as e:
      print(f"Erro de integridade ao inserir dados em 'pedidos': {e}")
    except sqlite3.Error as e:
      print(f"Erro ao inserir dados em 'pedidos': {e}")

    # Consultar dados
    try:
      cursor.execute("""
       SELECT v.nome, p.produto, p.quantidade
       FROM vendedores v
       JOIN pedidos p ON v.id = p.vendedor_id
      """)
      resultados = cursor.fetchall()
      for linha in resultados:
        print(f"Vendedor: {linha[0]}, Produto: {linha[1]}, Quantidade: {linha[2]}")
    except sqlite3.Error as e:
      print(f"Erro ao consultar dados: {e}")

  except sqlite3.Error as e:
    print(f"Erro ao conectar ao banco de dados: {e}")
  finally:
  # Fechar a conexão com o banco de dados
    if conn:
      conn.close()
      print("Conexão com o banco de dados fechada.")

main()

#Exemplo de funcionamento do SQLite3 com Python

"""""
# Importanto o módulo sqlite3
import sqlite3

# Criando a conexão com o banco de dados
conn = sqlite3.connect('meu-banco.db')

# Criando o cursor
cursor = conn.cursor()

# Executando declarações SQL
cursor.execute('declarações SQL estarão aqui') # Mais sobre isso na sequência

# (Quando forem realizadas consultas)
cursor.execute('uma declaração SELECT aqui') # Mais sobre isso na sequência
consulta = cursor.fetchall()
print(consulta)

# Confirmando as alterações realizadas
conn.commit()

# Fechando o cursor e a conexão
cursor.close()
conn.close()

"""