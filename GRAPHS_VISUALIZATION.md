# 📊 Gráficos e Visualização em Tempo Real

## ✨ Novos Recursos Visuais

### 1. 📈 **Gráfico de Velocidade em Tempo Real**

#### O que é?
Um gráfico interativo que mostra a velocidade de cópia em tempo real, atualizado a cada arquivo copiado.

#### Características:
- **Tipo**: Gráfico de linha com área preenchida
- **Eixo X**: Tempo decorrido em segundos
- **Eixo Y**: Velocidade em MB/s
- **Cores**: Azul para linha, mais claro para área
- **Máximo de Pontos**: 30 (últimos 30 arquivos)
- **Estatística**: Mostra velocidade média em tempo real

#### Como Usar:
1. Inicie uma cópia/movimento
2. O gráfico começará a aparecer após o primeiro arquivo
3. Observe a velocidade aumentar/diminuir conforme os arquivos são copiados
4. A velocidade média é exibida no canto superior esquerdo do gráfico

#### Interpretando o Gráfico:
```
↑ Linha subindo = Velocidade aumentando
↓ Linha descendo = Velocidade diminuindo  
╱ Linha reta inclinada = Velocidade constante
━ Linha horizontal = Velocidade estável
```

#### Exemplo:
```
Velocidade de Cópia em Tempo Real
250 ┤     ╱╲
    │    ╱  ╲
200 ┤   ╱    ╲╱
    │  ╱        ╲
150 ┤╱           ╲
    │              ╲
100 ┤                 ≈≈≈
    └─────────────────────
      0  10  20  30  40  50
        Tempo (s)
        
Velocidade Média: 175.5 MB/s
```

---

### 2. 📂 **Lista de Arquivos em Progresso**

#### O que é?
Uma lista que mostra os arquivos sendo copiados em tempo real, com os mais recentes no topo.

#### Características:
- **Máximo de Itens Visíveis**: 10 arquivos
- **Ordem**: Mais recentes no topo
- **Símbolo**: ✓ indica arquivo copiado com sucesso
- **Atualização**: A cada arquivo copiado
- **Scroll**: Automático para novos itens

#### Como Usar:
1. Inicie uma cópia/movimento
2. Os arquivos aparecerão na lista conforme são copiados
3. Os mais recentes aparecem no topo
4. Quando atingir 10 itens, o mais antigo é removido

#### Exemplo de Lista:
```
✓ relatorio_final.docx
✓ apresentacao_2024.pptx
✓ planilha_vendas.xlsx
✓ foto_evento_5.jpg
✓ foto_evento_4.jpg
✓ foto_evento_3.jpg
✓ foto_evento_2.jpg
✓ foto_evento_1.jpg
✓ video_tutorial.mp4
✓ manual_usuario.pdf
```

---

## 🎨 Layout Visual

### Aba "Copiar Arquivos"
```
┌─ Copiar Arquivos ──────────────────┐
│                                    │
│ Caminho de Origem:  [__________]   │
│ Caminho de Destino: [__________]   │
│                                    │
│ [▶ Iniciar] [⏸ Pausar] [⏹ Cancelar]│
│                                    │
│ Progresso: [████████░░░] 65%       │
│ Arquivo: foto.jpg | Vel: 125 MB/s │
│ Arquivos: 150/300 | Tamanho: ...   │
│                                    │
│ 📊 Gráfico de Velocidade:         │
│  250 ┤     ╱╲                      │
│  200 ┤    ╱  ╲                     │
│  150 ┤   ╱    ╲    Vel Média:     │
│  100 ┤  ╱      ╲                   │
│      └─────────                    │
│      Vel Média: 175.5 MB/s         │
│                                    │
│ 📂 Arquivos em Progresso:          │
│ ✓ foto_500.jpg                    │
│ ✓ foto_499.jpg                    │
│ ✓ foto_498.jpg                    │
│ ✓ foto_497.jpg                    │
│                                    │
└────────────────────────────────────┘
```

---

## 🔧 Implementação Técnica

### Classe `SpeedGraphWidget`

```python
class SpeedGraphWidget(FigureCanvas):
    """Widget de gráfico de velocidade em tempo real"""
    
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(8, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.speeds = deque(maxlen=30)  # Últimos 30 pontos
        self.times = deque(maxlen=30)
    
    def update_speed(self, elapsed_time, speed_mbps):
        """Atualiza o gráfico com novo ponto"""
        self.times.append(elapsed_time)
        self.speeds.append(speed_mbps)
        # Redesenha o gráfico...
    
    def reset(self):
        """Limpa o gráfico"""
        self.speeds.clear()
        self.times.clear()
```

### Dados Enviados pelo Backend

```python
# A cada arquivo copiado
{
    "elapsed_time": 23.5,        # Tempo decorrido
    "speed_mbps": 145.3,         # Velocidade atual
    "current_file": "foto.jpg",  # Nome do arquivo
    "files_copied": 150,         # Arquivos copiados
    "total_files": 300           # Total a copiar
}
```

### Atualização em Tempo Real

```python
def on_copy_progress(self, data):
    # Atualizar gráfico
    self.speed_graph.update_speed(
        data['elapsed_time'], 
        data['speed_mbps']
    )
    
    # Atualizar lista
    self.files_list.insertItem(0, f"✓ {data['current_file']}")
```

---

## 📊 Funcionalidades Avançadas

### Estatísticas do Gráfico

O gráfico mostra automaticamente:
- **Velocidade Mínima**: Ponto mais baixo da linha
- **Velocidade Máxima**: Ponto mais alto da linha
- **Velocidade Média**: Exibida no canto superior esquerdo
- **Tendência**: Se está aumentando ou diminuindo

### Comportamento da Lista

- **Novo item**: Aparece no topo quando arquivo termina
- **Remoção automática**: Quando atinge 10 itens
- **Scroll automático**: Para manter visível os novos itens
- **Sem duplicação**: Cada arquivo é listado uma vez

---

## 🎯 Casos de Uso

### 1. Monitorar Velocidade
```
"Por que a cópia está lenta?"
→ Olhe para o gráfico
→ Se a linha está para baixo, velocidade reduzida
→ Se tem picos, velocidade varia
```

### 2. Verificar Progresso
```
"Quais arquivos já foram copiados?"
→ Liste mostra os últimos 10 arquivos
→ ✓ indica sucesso
```

### 3. Detectar Problemas
```
"Há algum arquivo travando?"
→ Se gráfico fica preso em um valor baixo
→ Se lista não atualiza por tempo
```

---

## 🚀 Otimizações

### Performance
- Gráfico limitado a 30 pontos (evita lag)
- Lista limitada a 10 itens visíveis
- Atualização apenas quando há novo arquivo
- Matplotlib com backend Qt5Agg (otimizado)

### Memória
- Usa `deque` com `maxlen` (limite automático)
- Remove itens antigos automaticamente
- Não armazena histórico completo

### Visuais
- Gráfico atualiza suavemente
- Lista scroll automático
- Sem pisca ou flickering

---

## 📁 Arquivos Modificados

1. **main.py**
   - Importar `matplotlib` e `deque`
   - Classe `SpeedGraphWidget`
   - Adicionar gráfico em cada aba
   - Atualizar métodos de progresso

2. **requirements.txt**
   - Adicionar `matplotlib==3.8.2`

---

## 🎨 Customizações Possíveis

### Cores do Gráfico
```python
# Mudar cor da linha
self.ax.plot(..., color='#3498db')  # Azul PyQt

# Mudar cor da área
self.ax.fill_between(..., color='#3498db', alpha=0.2)
```

### Tamanho da Lista
```python
# Aumentar para 20 itens visíveis
self.files_list.setMaximumHeight(300)  # Altura em pixels

# Limitar a 5 items
if self.files_list.count() > 5:
    self.files_list.takeItem(5)
```

### Intervalo do Gráfico
```python
# Mostrar últimos 50 pontos em vez de 30
self.speeds = deque(maxlen=50)
self.times = deque(maxlen=50)
```

---

## 🧪 Testando os Gráficos

### Teste 1: Gráfico de Velocidade
```
1. Copie 100+ arquivos pequenos
2. Observe a linha aumentar e diminuir
3. Verifique a velocidade média no gráfico
4. Observe picos quando copia múltiplos arquivos
```

### Teste 2: Lista de Arquivos
```
1. Copie vários arquivos
2. Veja o nome do arquivo na lista
3. Confirme que os últimos aparecem no topo
4. Verifique que limite é 10 itens
```

### Teste 3: Reset após Conclusão
```
1. Inicie uma cópia
2. Observe o gráfico preencherse
3. Aguarde conclusão
4. Verifique que gráfico foi resetado
5. Verifique que lista foi limpa
```

---

## 📝 Notas Importantes

### Matplotlib no PyQt6
- Integrado via `FigureCanvasQTAgg`
- Renderização suave e responsiva
- Sem dependências adicionais além de matplotlib

### Deque (Double-Ended Queue)
- Estrutura de dados otimizada
- Com `maxlen`, remove automaticamente itens antigos
- Mais eficiente que listas Python comuns

### Performance em Arquivos Grandes
- Gráfico continua responsivo mesmo com cópias grandes
- Lista não perde performance com muitos arquivos
- Threading mantém UI fluida

---

**Copy Assistant Pro v2.1** - Com visualização em tempo real! 📊

Agora você pode monitorar graficamente o progresso das suas cópias!
