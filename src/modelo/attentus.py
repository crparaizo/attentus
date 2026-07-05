import pandas as pd
from itertools import product
import pulp as plp
from utilidades.utils import retorna_lista

def attentus(df_nan: pd.DataFrame, 
             df_nad: pd.DataFrame, 
             minutos_dividir: int) -> plp.LpProblem:
    """
    Função para resolver o problema de otimização de atendentes

    Args:
        df_nan (pd.DataFrame): DataFrame com a quantidade de NANs. (obrigatório)
        
        df_nad (pd.DataFrame): DataFrame com os regimes e Números de Atendentes 
        Disponíveis. (obrigatório)

    Returns:
        pd.DataFrame: DataFrame com os resultados da otimização
    """
    prob = plp.LpProblem(name="Attentus", sense=plp.LpMinimize)

    regimes = df_nad["regime"].to_dict()
    inicios = df_nan["hora_inicio"].to_dict()

    lista_variaveis = list(product(regimes, inicios))
    pulp_variaveis = plp.LpVariable.dicts(
        "A",
        lista_variaveis,
        lowBound=0,
        cat=plp.LpInteger
    )

    coeficientes = []
    for indice_regime, _ in lista_variaveis:
        encargo = df_nad.loc[indice_regime, "enc"]
        coeficientes.append(encargo)

    fo = plp.lpSum([coef * pulp_variaveis[var] 
                for coef, var in zip(coeficientes, lista_variaveis)])
    prob += fo, "FO"

    # RESTRIÇÃO 1
    # a quantidade de atendentes utilizados para cada regime deve ser menor ou igual ao 
    # nad (Número de Atendentes Disponíveis) de cada regime
    i = 0
    for indice_regime, horas_regime in regimes.items():
        nad = df_nad.loc[indice_regime, "nad"]

        linha = []
        for indice_inicio in inicios.keys():
            variavel_tupla = (indice_regime, indice_inicio)
            variavel_pulp = pulp_variaveis[variavel_tupla]
            linha.append(variavel_pulp)
        
        # print(linha, "<=", nad)
        prob += plp.lpSum(linha) <= nad, f"01_{i:03}"
        i += 1

    # RESTRIÇÃO 2
    # a quantidade de atendentes utilizados para cada período do dia deve ser maior ou igual
    # ao nan (Número de Atendentes Necessários) de cada período do dia
    for j in inicios:
        nan = df_nan.loc[j, "nan"]

        linha = []
        for indice_regime, regime in regimes.items():
            tamanho = int(regime * 60 / minutos_dividir)
            lista = retorna_lista(j=j + 1, tamanho=tamanho, 
                                  lista_momentos=list(inicios.keys()))

            linha += [pulp_variaveis[(indice_regime, k)] for k in lista]
        
        nome_restricao = f"02_{j:03}"
        prob += plp.lpSum(linha) >= nan, nome_restricao

    solver = plp.getSolver("PULP_CBC_CMD")
    prob.solve(solver=solver)

    return prob