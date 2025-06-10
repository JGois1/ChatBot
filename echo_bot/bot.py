# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import aiohttp
from datetime import datetime
from botbuilder.core import (
    ActivityHandler,
    TurnContext,
    MessageFactory,
    BotState,
    ConversationState,
)
from botbuilder.schema import (
    ChannelAccount,
    CardAction,
    ActionTypes,
    SuggestedActions,
)


class MyBot(ActivityHandler):
    def __init__(self, conversation_state: BotState):
        self.conversation_state = conversation_state
        self.flow_accessor = self.conversation_state.create_property("DialogFlow")

    async def on_turn(self, turn_context: TurnContext):
        await super().on_turn(turn_context)
        await self.conversation_state.save_changes(turn_context)

    async def on_message_activity(self, turn_context: TurnContext):
        flow = await self.flow_accessor.get(turn_context, lambda: {"last_question": None})
        texto_do_usuario = turn_context.activity.text.lower()

        # LÓGICA PRINCIPAL: Verifica se o bot estava esperando uma resposta
        if flow.get("last_question") == "ask_order_id":
            await self.flow_accessor.set(turn_context, {"last_question": None})
            await self._handle_order_id_response(turn_context, texto_do_usuario)
        
        # --- NOVO BLOCO PARA TRATAR A RESPOSTA DE PRODUTOS ---
        elif flow.get("last_question") == "ask_product_info":
            await self.flow_accessor.set(turn_context, {"last_question": None})
            await self._handle_product_info_response(turn_context, texto_do_usuario)
        
        # Se não, processa o comando do menu
        else:
            if "oi" in texto_do_usuario or "olá" in texto_do_usuario or "menu" in texto_do_usuario:
                await self._show_main_menu(turn_context)

            # --- BLOCO MODIFICADO PARA PRODUTOS ---
            elif texto_do_usuario == "consultar produtos":
                await turn_context.send_activity("Ok! Para consultar um produto, por favor, me diga o ID e a categoria no formato: `id=SEU_ID categoria=SUA_CATEGORIA`")
                await self.flow_accessor.set(turn_context, {"last_question": "ask_product_info"})
            
            elif texto_do_usuario == "consultar pedido":
                await turn_context.send_activity("Ok! Por favor, me diga o ID do pedido que você quer consultar.")
                await self.flow_accessor.set(turn_context, {"last_question": "ask_order_id"})

            else:
                await turn_context.send_activity("Desculpe, não entendi. Diga 'oi' ou 'menu' para ver as opções.")

    # --- MÉTODOS AUXILIARES ---

    async def _show_main_menu(self, turn_context: TurnContext):
        """Mostra o menu principal com botões."""
        text = "Olá! Eu sou o assistente do e-commerce. Como posso te ajudar hoje?"
        actions = [
            CardAction(type=ActionTypes.im_back, title="Consultar Produtos", value="consultar produtos"),
            CardAction(type=ActionTypes.im_back, title="Consultar Pedido", value="consultar pedido"),
            CardAction(type=ActionTypes.im_back, title="Extrato de Compras", value="extrato de compras"),
            CardAction(type=ActionTypes.im_back, title="Comprar Produto", value="comprar produto"),
        ]
        reply = MessageFactory.text(text)
        reply.suggested_actions = SuggestedActions(actions=actions)
        await turn_context.send_activity(reply)

    async def _handle_order_id_response(self, turn_context: TurnContext, pedido_id: str):
        """Pega o ID do pedido e faz a chamada para a API Java de Pedidos."""
        try:
            if not pedido_id.isdigit():
                await turn_context.send_activity("Isso não parece ser um ID válido. Por favor, envie apenas o número do pedido.")
                return

            # --- URL CORRIGIDA ---
            url = f"https://cloud-ecommerce02.documents.azure.com:443/{pedido_id}"
            await turn_context.send_activity(f"Entendido! Buscando informações do pedido {pedido_id}... ⏳")

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        pedido = await response.json()
                        # ... (resto da formatação da resposta do pedido)
                        user_info = pedido.get('user')
                        user_id_str = str(user_info.get('id')) if user_info else "Não informado"
                        data_formatada = "Data não informada"
                        if pedido.get('dataPedido'):
                            dt_obj = datetime.fromisoformat(pedido.get('dataPedido'))
                            data_formatada = dt_obj.strftime('%d/%m/%Y às %H:%M')
                        resposta_final = (
                            f"✅ **Pedido Encontrado!**\n\n"
                            f"ID do Pedido: {pedido.get('id')}\n"
                            f"Status: {pedido.get('status')}\n"
                            f"Valor Total: R$ {pedido.get('total')}\n"
                            f"Data do Pedido: {data_formatada}\n"
                            f"ID do Usuário: {user_id_str}"
                        )
                        await turn_context.send_activity(resposta_final)
                    elif response.status == 404:
                        await turn_context.send_activity(f"❌ Pedido com ID `{pedido_id}` não foi encontrado.")
                    else:
                        await turn_context.send_activity(f"😕 Houve um problema ao contatar a API. Status: {response.status}")
        except Exception as e:
            print(f"Erro ao processar o pedido: {e}")
            await turn_context.send_activity("Ocorreu um erro. Por favor, tente novamente.")
    
    # --- NOVO MÉTODO AUXILIAR PARA PRODUTOS ---
    async def _handle_product_info_response(self, turn_context: TurnContext, user_input: str):
        """Pega o ID e categoria do produto e faz a chamada para a API Java de Produtos."""
        try:
            # Extrai as informações do input. Ex: "id=123 categoria=eletronicos"
            partes = user_input.split()
            produto_id = partes[0].replace("id=", "")
            categoria = partes[1].replace("categoria=", "")

            url = f"https://cloud-ecommerce02.documents.azure.com:443/{produto_id}?categoria={categoria}"
            await turn_context.send_activity(f"Entendido! Buscando informações do produto {produto_id}... ⏳")

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        produto = await response.json()
                        resposta_formatada = (
                            f"✅ **Produto Encontrado!**\n\n"
                            f"**Nome:** {produto.get('nome')}\n"
                            f"**Preço:** R$ {produto.get('preco')}\n"
                            f"**Estoque:** {produto.get('estoque')} unidades\n"
                            f"**Descrição:** {produto.get('descricao')}"
                        )
                        await turn_context.send_activity(resposta_formatada)
                    elif response.status == 404:
                        await turn_context.send_activity(f"❌ Produto com ID `{produto_id}` e categoria `{categoria}` não foi encontrado.")
                    else:
                        await turn_context.send_activity(f"😕 Houve um problema ao contatar a API. Status: {response.status}")
        except Exception as e:
            print(f"Erro ao processar o produto: {e}")
            await turn_context.send_activity("Formato de comando incorreto. Por favor, use: `id=SEU_ID categoria=SUA_CATEGORIA`")