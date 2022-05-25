from py_pdf_parser.loaders import load_file
from py_pdf_parser.visualise import visualise
import tabula, re, json, glob, numpy
from pandas import concat

class ExtractTabel:
  def __init__(self, path):
    self.path         = path
    self.FONT_MAPPING = {      
      'Arial,Bold,11.0'    : 'titulo',
      'Arial,9.1'          : 'subtitulo',
      'Arial,9.0'          : 'subtitulo',
      'Times New Roman,9.1': 'subtitulo',
      'Arial,Bold,7.9'     : 'coluna',
      'Arial,Bold,7.0'     : 'coluna',
      'Arial,Bold,8.0'     : 'coluna',
      'Arial,7.9'          : 'conteudo',
      'Arial,Bold,12.0'    : 'titulo_tabela',
      'Arial,12.0'         : 'texto'
      }
    self.document          = load_file(self.path, font_mapping=self.FONT_MAPPING)
    self.tables            = self.extract_tables()
    self.get_summary_pages = self._get_summary_pages()
    self.table_pages       = self._get_summary_tables_pages()
    self.paginas_tabela    = self._get_num_summary_tables_pages()


  def _get_summary_pages(self):
    """ Extrai as páginas em que as tabelas, os relatórios e as notas explicativas
    estão no pdf a partir do sumário do mesmo


    Returns:
        Dict: Contém como chave o nome do item e como valor o número da página
    """
    summary                      = self.document.get_page(1)
    df_individual_element        = (
        summary.elements.filter_by_font("titulo")
        .filter_by_text_equal("DFs Individuais")
        .extract_single_element()
    )
    pareceres_declaracoes_element = (
        summary.elements.filter_by_font("titulo")
        .filter_by_text_equal("Pareceres e Declarações")
        .extract_single_element()
    )
    order_summary_section = self.document.sectioning.create_section(
        name="sumario",
        start_element=df_individual_element,
        end_element=pareceres_declaracoes_element,
        include_last_element=False
    )
    d           = {}
    page        = []
    tables_name = []
    for idx,i in enumerate(order_summary_section.elements.filter_by_font('subtitulo')):
      pages      = re.match(r'\d+', i.text())
      table_name = re.match(r'[A-Za-z]+.+', i.text())
      if pages != None:
        page.append(int(pages.group()))
      else:
        tables_name.append(table_name.group() + str(f' {idx}'))

    for i in range(len(page)):
      d[tables_name[i]] = page[i]

    return d

  def _get_summary_tables_pages(self):
    """Cria uma seção dentro do sumário com os indíce das tabelas

    Returns:
        Dict: dicionário com o nome do indíce e o valor da página correspondente
    """
    summary                      = self.document.get_page(1)
    df_individual_element        = (
        summary.elements.filter_by_font("titulo")
        .filter_by_text_equal("DFs Individuais")
        .extract_single_element()
    )
    
    pareceres_declaracoes_element = (
        summary.elements.filter_by_font("subtitulo")
        .filter_by_text_equal("Notas Explicativas")
        .extract_single_element()
    )

    order_summary_section = self.document.sectioning.create_section(
        name="tabelas",
        start_element=df_individual_element,
        end_element=pareceres_declaracoes_element,
        include_last_element=False
    )

    d           = {}
    page        = []
    tables_name = []
    for idx,i in enumerate(order_summary_section.elements.filter_by_font('subtitulo')):
      pages      = re.match(r'\d+', i.text())
      table_name = re.match(r'[A-Za-z]+.+', i.text())
      if pages != None:
        page.append(int(pages.group()))
      else:
        tables_name.append(table_name.group() + str(f' {idx}'))

    for i in range(len(page)):
      d[tables_name[i]] = page[i]

    return d

  
  def _get_num_summary_tables_pages(self):
    """ Extrai apenas as páginas que contém tabelas no pdf

    Returns:
        List: Uma lista com o número das páginas referentes à tabelas (DFs e DMP) do pdf
    """
    d = self._get_summary_tables_pages()
    keys = [k for k,v in d.items()]
    d_filter = [{v: d[v]} for i,v in enumerate(keys)]
    if len(self.document.get_page(2).elements.filter_by_regex(r'.ndice')) == 0:
      numero_pagina =  [list(i.values())[0]+1 for i in d_filter]
    else:
      numero_pagina =  [list(i.values())[0]+2 for i in d_filter]
    d.popitem()
    len_tabela = list(numpy.diff(numero_pagina))
    numero_pagina.pop()
    d1 = {}
    for idx, key in enumerate(d.keys()):
      d1[key] = (numero_pagina[idx], len_tabela[idx])
    return d1

    
  def _get_dmpl_columns_names(self, page):
    """ Separa as tabelas de "Demonstração das Mutações do Patrimônio Líquido"
        e corrige o nome das colunas colocandos-as na ordem correta

    Args:
        page (int): número da página que contém a tabela 

    Returns:
        Lista: Contém strings com os nomes das colunas da tabela DMP seguindo a ordem do pdf
    """
    with open("dicio_colunas_dfp.json") as file:
      data = json.load(file)

    table = tabula.read_pdf(self.path,pages=page)[0]
    table = table.drop([table.index[0], table.index[1]])
    if len(table.columns) == 8:
      resultado = data['Demonstração das Mutações do Patrimônio Líquido 0']
    elif len(table.columns) == 9:
      resultado = data['Demonstração das Mutações do Patrimônio Líquido 1']
    elif len(table.columns) == 10:
      resultado = data['Demonstração das Mutações do Patrimônio Líquido 2']
  
    return resultado

  
  def _get_dfs_columns_names(self, page):
    """Separa as tabelas de "Demonstração Financeira Individual ou Consolidada" 
        e corrige o nome das colunas colocandos-as na ordem correta
    Args:
        page (int): número da página que contém a tabela 

    Returns:
        List: Contém strings com os nomes das colunas da tabela DF seguindo a ordem do pdf
    """
    with open("dicio_colunas_dfp.json") as file:
      dicio = json.load(file)
    summary_pages = self._get_summary_pages()
    padrao        = r"\d\d\/\d\d\/\d\d\d\d.+\d\d\/\d\d\/\d\d\d\d"
    data          = [re.search(padrao, value).group() for value in summary_pages.keys() if 'DMPL' in value]
    data          = [value for idx,value in enumerate(data) if idx <= 2]
    padrao_year = r'\d\d\d\d'
    ultimo_valor = int(re.search(padrao_year, data[-1]).group())
    if len(data) <= 2:
      data.append(f'01/01/{ultimo_valor-1} à 31/12/{ultimo_valor-1}')
    coluna_names  = [i for i in dicio['Balanço Patrimonial Ativo'] if "{}" not in i]
    [coluna_names.append(value.format(data[idx])) for idx, value in enumerate(dicio['Balanço Patrimonial Ativo'][-3:])]
    return coluna_names


  def get_table_name(self, page):
    """ Extrai o nome das tabelas
    Args:
        page (int): número da página que contém a tabela 

    Returns:
        String: Contém o nome da tabela referente à página supracitada
    """
    document      = self.document.get_page(page)
    titulo_tabela = (
      document.elements.filter_by_font("titulo_tabela")
    )
    return titulo_tabela[0]


  def get_table(self, page):
    """ Realiza a busca completa das tabelas, filtrando-as segundo seu tipo e limpando 
    caso tenha necessidade 
    Args:
        page (int): número da página que contém a tabela 

    Returns:
        DataFrame
    """
    try:
      table = tabula.read_pdf(self.path,pages=page)[0]
      table = table.drop([table.index[0], table.index[1]])
      if 'Demonstração das Mutações' in self.get_table_name(page).text():
        table = table.set_axis(self._get_dmpl_columns_names(page), axis=1)
      else:
        table = table.set_axis(self._get_dfs_columns_names(page), axis=1)
      
      return table
    except:
      pass
  
  
  def extract_tables(self):
    """ Realiza a extração completa das tabelas devolvendo uma lista de DataFrames

    Returns:
        Dict: Contém um dicionário com o nome da tabela com chave e o DataFrame correspondente
    """
    dicio = self._get_num_summary_tables_pages()
    d = {}
    for k,v in dicio.items():
      lista = [self.get_table(i) for i in range(v[0], v[0]+v[-1])]
      tabela = concat(lista, ignore_index=True)
      d[self.get_table_name(v[0]).text()] = tabela
    return d  


# lista_pdfs = glob.glob("*.pdf")

# for idx, file in enumerate(lista_pdfs):
#  try:
#    e = ExtractTabel(file)
#    dicio = e.extract_tables()
#    print(f'{idx}: Deu certo, a quantidade de dfs é: ')
#    print(len(dicio))
#    print('-------')
#  except:
#     print(idx, file)
