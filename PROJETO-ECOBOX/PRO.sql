-- Combined SQL file (portable version)
-- Created from your dump on 2025-12-01

CREATE DATABASE IF NOT EXISTS `ecobox` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `ecobox`;

-- Table: admins
DROP TABLE IF EXISTS `admins`;
CREATE TABLE `admins` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nome` varchar(100) NOT NULL,
  `email` varchar(120) NOT NULL,
  `senha` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `admins` VALUES (1,'Administrador','admin@admin.com','admin123');

-- Table: carrinho
DROP TABLE IF EXISTS `carrinho`;
CREATE TABLE `carrinho` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `usuario_id` int(11) NOT NULL,
  `produto_id` int(11) NOT NULL,
  `quantidade` int(11) DEFAULT 1,
  `preco_unitario` decimal(10,2) NOT NULL,
  `total` decimal(10,2) GENERATED ALWAYS AS (`quantidade` * `preco_unitario`) STORED,
  `data_adicionado` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `usuario_id` (`usuario_id`),
  KEY `produto_id` (`produto_id`),
  CONSTRAINT `carrinho_ibfk_1` FOREIGN KEY (`usuario_id`) REFERENCES `cliente` (`id`) ON DELETE CASCADE,
  CONSTRAINT `carrinho_ibfk_2` FOREIGN KEY (`produto_id`) REFERENCES `produtos` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `carrinho` (`id`, `usuario_id`, `produto_id`, `quantidade`, `preco_unitario`, `data_adicionado`) VALUES
(9,1,3,3,129.90,'2025-12-01 03:38:40'),
(14,13,4,1,64.90,'2025-12-01 16:12:43');

-- Table: cliente
DROP TABLE IF EXISTS `cliente`;
CREATE TABLE `cliente` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nome` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `senha` varchar(255) NOT NULL,
  `tipo` enum('cliente','admin') DEFAULT 'cliente',
  `foto_usuario` varchar(255) DEFAULT 'static/img/padrao_foto.png',
  `pais_regiao` varchar(5) DEFAULT 'br',
  `horas_online` int(11) DEFAULT 0,
  `receber_promocoes` tinyint(1) DEFAULT 1,
  `notificacoes_pedido` tinyint(1) DEFAULT 1,
  `alertas_seguranca` tinyint(1) DEFAULT 1,
  `status` enum('ativo','inativo','bloqueado') DEFAULT 'ativo',
  `total_gasto` decimal(12,2) DEFAULT 0.00,
  `total_pedidos` int(11) DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Table: cliente_historico
DROP TABLE IF EXISTS `cliente_historico`;
CREATE TABLE `cliente_historico` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cliente_id` int(11) NOT NULL,
  `admin_id` int(11) DEFAULT NULL,
  `acao` varchar(120) NOT NULL,
  `detalhes` text DEFAULT NULL,
  `ip_origem` varchar(50) DEFAULT NULL,
  `meta` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`meta`)),
  `criado_em` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `cliente_id` (`cliente_id`),
  CONSTRAINT `cliente_historico_ibfk_1` FOREIGN KEY (`cliente_id`) REFERENCES `cliente` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Table: feedbacks
DROP TABLE IF EXISTS `feedbacks`;
CREATE TABLE `feedbacks` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `mensagem` text NOT NULL,
  `data_envio` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Table: metodo_pagamento
DROP TABLE IF EXISTS `metodo_pagamento`;
CREATE TABLE `metodo_pagamento` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cliente_id` int(11) NOT NULL,
  `tipo` varchar(20) NOT NULL,
  `bandeira` varchar(30) DEFAULT NULL,
  `ultimos4` varchar(4) DEFAULT NULL,
  `nome_titular` varchar(120) DEFAULT NULL,
  `expiracao` varchar(7) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `eh_padrao` tinyint(1) DEFAULT 0,
  `criado_em` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `cliente_id` (`cliente_id`),
  CONSTRAINT `metodo_pagamento_ibfk_1` FOREIGN KEY (`cliente_id`) REFERENCES `cliente` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Table: pedido_itens
DROP TABLE IF EXISTS `pedido_itens`;
CREATE TABLE `pedido_itens` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `pedido_id` int(11) DEFAULT NULL,
  `produto_id` int(11) DEFAULT NULL,
  `quantidade` int(11) DEFAULT NULL,
  `preco_unitario` decimal(10,2) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Table: pedidos
DROP TABLE IF EXISTS `pedidos`;
CREATE TABLE `pedidos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cliente_id` int(11) DEFAULT NULL,
  `total` decimal(10,2) DEFAULT NULL,
  `data_` datetime DEFAULT NULL,
  `status` enum('pendente','processando','enviado','entregue','cancelado') DEFAULT 'pendente',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Table: pedidos_cancelados
DROP TABLE IF EXISTS `pedidos_cancelados`;
CREATE TABLE `pedidos_cancelados` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `pedido_id` int(11) NOT NULL,
  `cliente_id` int(11) NOT NULL,
  `cliente_nome` varchar(150) DEFAULT NULL,
  `cliente_email` varchar(150) DEFAULT NULL,
  `total` decimal(10,2) DEFAULT NULL,
  `status_antigo` varchar(50) DEFAULT NULL,
  `data_pedido` datetime DEFAULT NULL,
  `data_cancelado` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- (no inserts for pedidos_cancelados in dump)

-- Table: produtos
DROP TABLE IF EXISTS `produtos`;
CREATE TABLE `produtos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nome` varchar(100) NOT NULL,
  `descricao` text DEFAULT NULL,
  `preco` decimal(10,2) NOT NULL,
  `imagem` varchar(255) DEFAULT 'static/img/default.png',
  `estoque` int(11) DEFAULT 0,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `produtos` VALUES
(1,'EcoBox Pro','Modelo de alta resistência da EcoBox, ideal para uso comercial em feiras, lojas ou para transporte de cargas mais pesadas, na cor cinza grafite.',139.90,'ecobox_pro_cinza_grafite.png',12),
(2,'Caixa de Bambu','Caixa super sustentável e reutilizável',90.90,'produto1.png',13),
(3,'Caixa Premium','Caixa tradicional Reforçada de mais qualidade',129.90,'produto_premium.png',9),
(4,'EcoBox Mini','Versão compacta da EcoBox, perfeita para pequenos espaços, carros ou escritórios, na elegante cor verde oliva.',64.90,'ecobox_mini.png',25),
(5,'EcoBox Original','A caixa multifuncional dobrável feita de plástico reciclado e bambu, ideal para organizar, transportar e como assento ou mesa.',89.90,'ecobox_original.png',45),
(6, 'Ecobox Laranja', 'Sustentabilidade e estilo em um só recipiente. Corpo ecológico, perfeita para organizar sua vida com consciência ambiental.', 39,90,'ecobox_la.png',20);

-- Table: reset_senha
DROP TABLE IF EXISTS `reset_senha`;
CREATE TABLE `reset_senha` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `token` varchar(255) NOT NULL,
  `expira_em` datetime NOT NULL,
  `usado` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `reset_senha_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `cliente` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- End of SQL
