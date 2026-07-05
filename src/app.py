import streamlit as st
import pandas as pd
from io import BytesIO
from pulp import LpStatus
from utilidades.utils import (gerar_tabela_nan,
                              ajusta_polinomio,
                              encontra_divisores, 
                              lista_turnos_possiveis,
                              gera_tabelas,
                              gera_resultados)

from modelo.attentus import attentus

def main():
    st.title("Attentus")
    st.sidebar.title("Configurações")

    qtd_horas_total = st.sidebar.number_input(
        "Quantidade de horas totais do dia para trabalhar",
        min_value=1, max_value=48, value=24, step=1,
        help="Ajuda sobre este campo")
    
    st.sidebar.divider()
    # ---------------------------------------------------------------------------------

    colunas = st.sidebar.columns([1, 1])
    hora_inicial = colunas[0].number_input(
        "Hora inicial do dia (0-23)",
        min_value=0, max_value=23, value=0, step=1)

    minuto_inicial = colunas[1].number_input(
        "Minuto inicial do dia (0-59)",
        min_value=0, max_value=59, value=0, step=1)
    
    st.sidebar.divider()
    # ---------------------------------------------------------------------------------

    qtd_minutos_total = qtd_horas_total * 60

    divisores = encontra_divisores(qtd_minutos_total)
    minutos_dividir = st.sidebar.selectbox(
        "Dividir o dia em quantos minutos?",
        options=divisores,
        index=divisores.index(15) if 15 in divisores else 0
    )

    st.sidebar.divider()
    # ---------------------------------------------------------------------------------

    turnos_possiveis = lista_turnos_possiveis(
        horas_minimas=1,
        horas_maximas=qtd_horas_total,
        minutos_dividir=minutos_dividir)
    
    dict_turnos_possiveis = {}
    for turno in turnos_possiveis:
        horas = int(turno)
        minutos = int((turno - horas) * 60)
        dict_turnos_possiveis[f"{horas:02}h{minutos:02}"] = turno
    
    qtd_turnos = st.sidebar.number_input(
        "Quantidade de turnos possíveis",
        min_value=1, max_value=5,
        value=3, step=1)
    
    turnos = []
    encargos = []
    nads = []
    for i in range(qtd_turnos):

        colunas = st.sidebar.columns(3)

        turno = colunas[0].selectbox(
            f"Turno {i + 1}",
            options=list(dict_turnos_possiveis.keys()),
            index=i)
        
        encargo = colunas[1].number_input(
            f"Encargo do turno {i + 1}",
            min_value=0.0, max_value=1000.0,
            value=540.0, step=0.1)
        
        nad = colunas[2].number_input(
            f"NAD do turno {turno}",
            min_value=0, max_value=200,
            value=200, step=1)

        turnos.append(dict_turnos_possiveis[turno])
        encargos.append(encargo)
        nads.append(nad)

    st.sidebar.divider()
    # ---------------------------------------------------------------------------------

    tempo_descanso = st.sidebar.number_input(
        "Tempo de descanso entre atendimentos (segundos)",
        min_value=0, max_value=1000, value=0, step=1)
    
    tempo_maximo_espera = st.sidebar.number_input(
        "Tempo máximo de espera para atendimento (segundos)",
        min_value=0, max_value=1000, value=10, step=1)
    
    grau_polinomio = st.sidebar.number_input(
        "Grau do polinômio para o modelo de previsão",
        min_value=1, max_value=10, value=2, step=1)

    st.sidebar.divider()
    # ---------------------------------------------------------------------------------

    df_nad, df_tabela_ligantes_vazia = gera_tabelas(qtd_horas_total, minutos_dividir,
                                                        hora_inicial, minuto_inicial,
                                                        turnos, encargos, nads)
    
    buffer = BytesIO()
    df_tabela_ligantes_vazia.to_excel(buffer, index=False)
    buffer.seek(0)
    
    st.sidebar.download_button(
        label="Download df_tabela_ligantes vazia",
        data=buffer,
        file_name='df_tabela_ligantes.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

    # importar o arquivo excel usando o streamlit e transformando em dataframe
    uploaded_file_duracoes = \
        st.sidebar.file_uploader("Carregar arquivo de durações preenchidas", 
                                 type=["csv", "xlsx"])
    if uploaded_file_duracoes is not None:
        df_duracoes = pd.read_excel(uploaded_file_duracoes)
        st.subheader("Tabela de Durações")
        df_duracoes = st.data_editor(df_duracoes, use_container_width=True)
    
    uploaded_file_ligantes = \
        st.sidebar.file_uploader("Carregar arquivo com número médio de ligantes preenchidas", 
                                 type=["csv", "xlsx"]
                                 )
    if uploaded_file_ligantes is not None:
        df_tabela_ligantes = pd.read_excel(uploaded_file_ligantes)
        st.subheader("Tabela de Ligantes")
        df_tabela_ligantes = st.data_editor(df_tabela_ligantes, use_container_width=True)

    st.sidebar.divider()
    # ---------------------------------------------------------------------------------

    opcao = st.sidebar.segmented_control(
        options=["Ajustar Polinômio", "Rodar Modelo"],
        label="Escolha uma opção",
        default="Ajustar Polinômio",
        selection_mode="single"
    )

    print(f"Opção selecionada: {opcao}")

    botao = st.sidebar.button("Avançar")

    if opcao == "Ajustar Polinômio" and botao == True and uploaded_file_duracoes:
        fig = ajusta_polinomio(df_duracoes, grau_polinomio)
        st.pyplot(fig)
    elif opcao == "Rodar Modelo" and botao == True and \
        uploaded_file_ligantes and uploaded_file_duracoes:
        
        coluna_nan = gerar_tabela_nan(df_tabela_ligantes=df_tabela_ligantes,
                                  df_duracoes=df_duracoes,
                                  tempo_maximo_espera=tempo_maximo_espera,
                                  tempo_descanso=tempo_descanso,
                                  g=grau_polinomio)
        
        df_tabela_ligantes["nan"] = coluna_nan

        prob = attentus(df_nan=df_tabela_ligantes,
                        df_nad=df_nad,
                        minutos_dividir=minutos_dividir)
        
        status = LpStatus[prob.status]

        if status != "Optimal":
            st.error(f"Erro ao resolver o modelo: {status}")
            return
        
        regimes = df_nad["regime"].to_dict()
        inicios = df_tabela_ligantes["hora_inicio"].to_dict()
        df_resultados = gera_resultados(prob, regimes, inicios)
        df_totais = df_resultados.sum(axis=0)

        st.subheader("Tabela das Escalas")
        st.dataframe(df_resultados)

        st.subheader("Total de Atendentes por Turno")
        st.dataframe(df_totais.reset_index(name='Total de Atendentes'), 
                     hide_index=True)
        st.success(f":streamlit: Custo Total: R$ {prob.objective.value():,.2f}")



if __name__ == "__main__":
    main()