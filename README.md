# Copy Assistant Pro 🚀

Aplicação Desktop Windows Profissional para Cópia de Arquivos

## 🎯 Funcionalidades

✅ **Cópia Inteligente**
- Cópia de arquivos e pastas com monitoramento em tempo real
- Validação de caminhos automática
- Proteção contra cópias recursivas

✅ **Relatórios Detalhados**
- Velocidade de cópia em MB/s
- Quantidade de arquivos copiados
- Tipos de arquivos copiados
- Tamanho total
- Tempo total de operação

✅ **Verificação de Leitura**
- Verifica se o arquivo pode ser lido por completo
- Relata arquivos inacessíveis ou inexistentes
- Não certifica a integridade do conteúdo sem checksum

✅ **Interface Desktop Profissional**
- Design moderno nativo Windows (PyQt6)
- Barra de progresso em tempo real
- Tema claro/escuro
- Histórico persistente
- Configurações personalizáveis
- File browser integrado

## 🛠️ Instalação

### Pré-requisitos
- Python 3.10+
- pip (gerenciador de pacotes Python)

### Passo 1: Instalar dependências

```bash
python -m pip install -r requirements.txt
```

### Passo 2: Executar a aplicação

**Opção A - Linha de comando:**
```bash
python main.py
```

**Opção B - Duplo clique em `run.bat`:**
```
run.bat
```

## 📖 Como Usar

### 1. Copiar Arquivos

1. Abra a aplicação
2. Na aba **"Copiar Arquivos"**, faça:
   - **Caminho de Origem**: Clique em "Procurar" ou digite o caminho
   - **Caminho de Destino**: Clique em "Procurar" ou digite o caminho
3. Clique em **"Iniciar Cópia"**
4. Acompanhe o progresso em tempo real:
   - Arquivo sendo copiado
   - Porcentagem de conclusão
   - Velocidade de cópia
   - Arquivos copiados / Total
5. Ao concluir, a aplicação mostrará um resumo com:
   - Total de arquivos copiados
   - Falhas (se houver)
   - Tamanho total
   - Tempo total
   - Velocidade média

### 2. Verificar Acesso a Arquivo

1. Vá para a aba **"Verificar Acesso"**
2. Informe o caminho do arquivo (ou use "Procurar")
3. Clique em **"Verificar Leitura"**
4. O sistema mostrará:
   - ✅ Arquivo acessível e lido por completo
   - ❌ Arquivo inacessível ou inexistente

### 3. Visualizar Histórico

Na aba **"Histórico"**, você verá todas as operações realizadas:
- Data e hora
- Pasta de origem
- Pasta de destino
- Quantidade de arquivos copiados
- Tamanho copiado
- Velocidade média

### 4. Configurações

Na aba **"Configurações"**, personalize:
- **Notificações**: Alertas ao concluir ou em erros
- **Comportamento**: Preservar data/hora dos arquivos, limpar formulário após cópia
- **Aparência**: Tema (Claro/Escuro/Automático)

## 📊 Informações do Sistema (Navbar)

A aplicação exibe em tempo real:
- **CPU**: Porcentagem de uso do processador
- **MEM**: Porcentagem de memória RAM em uso
- **DISK**: Porcentagem de espaço em disco utilizado

## 🏗️ Estrutura do Projeto

```
copiadetaladaepresonalizada/
├── main.py                    # Interface PyQt6 Desktop
├── copy_service.py           # Lógica de cópia (serviço)
├── requirements.txt          # Dependências Python
├── config.json              # Configurações da aplicação
├── history.json             # Histórico de operações
└── run.bat                  # Script para executar no Windows
```

## 🔧 Tecnologias Utilizadas

**Frontend:**
- PyQt6 - Interface gráfica nativa Windows
- Python 3.10+

**Backend (Serviço):**
- psutil - Informações do sistema
- pathlib - Manipulação de caminhos
- json - Persistência de dados
- threading - Operações assíncronas

## 📝 Exemplos de Uso

### Copiar uma pasta inteira
```
Origem: C:\Users\seu_usuario\Documentos
Destino: D:\Backup\Documentos
```

### Copiar um arquivo específico
```
Origem: C:\Users\seu_usuario\arquivo.zip
Destino: E:\Backup\arquivo.zip
```

## 🐛 Solução de Problemas

### "Caminho não encontrado"
- Verifique a ortografia do caminho
- Confirme que o caminho existe no sistema
- Use o botão "Procurar" para selecionar o caminho

### "Erro ao copiar"
- Verifique permissões do arquivo/pasta
- Confirme que há espaço em disco
- Feche programas que possam estar usando os arquivos

### A aplicação não inicia
- Verifique se Python 3.10+ está instalado: `python --version`
- Reinstale as dependências: `pip install -r requirements.txt --force-reinstall`
- Execute via linha de comando para ver mensagens de erro: `python main.py`

## 📄 Licença

Projeto desenvolvido como assistente profissional de cópia de arquivos.

---

**Copy Assistant Pro** - Simplificando cópias profissionais! 🎯
