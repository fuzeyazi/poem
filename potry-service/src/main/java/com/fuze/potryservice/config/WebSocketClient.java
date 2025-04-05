//package com.fuze.potryservice.config;
//
//import jakarta.websocket.*;
//
//import java.io.IOException;
//import java.net.URI;
//import java.net.URISyntaxException;
//
//@ClientEndpoint
//public class WebSocketClient {
//
//    private Session session;
//
//    public void connect(String uri) {
//        try {
//            WebSocketContainer container = ContainerProvider.getWebSocketContainer();
//            container.connectToServer(this, new URI(uri));
//        } catch (DeploymentException | URISyntaxException | IOException e) {
//            e.printStackTrace();
//        }
//    }
//
//    @OnOpen
//    public void onOpen(Session session) {
//        this.session = session;
//        System.out.println("WebSocket connection opened.");
//    }
//
//    @OnMessage
//    public void onMessage(String message) {
//        System.out.println("Received message: " + message);
//        try {
//            session.getBasicRemote().sendText("Hello, WebSocket!");
//        } catch (IOException e) {
//            e.printStackTrace();
//        }
//    }
//
//    @OnClose
//    public void onClose(Session session, CloseReason closeReason) {
//        System.out.println("WebSocket connection closed: " + closeReason);
//    }
//
//    @OnError
//    public void onError(Throwable error) {
//        System.out.println("WebSocket error: " + error.getMessage());
//    }
//}
