from datetime import date

DIA_LIMITE = (4, 2)  # 2 de abril


def calcular_prazo(apresentado_em: date) -> date:
    """Art. 100, §5º da Constituição: apresentado até 2 de abril, paga até 31/12 do
    ano seguinte; depois disso, até 31/12 do ano subsequente ao seguinte."""
    ate_o_limite = (apresentado_em.month, apresentado_em.day) <= DIA_LIMITE
    anos_de_prazo = 1 if ate_o_limite else 2
    return date(apresentado_em.year + anos_de_prazo, 12, 31)
