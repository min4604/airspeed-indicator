/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
I2C_HandleTypeDef hi2c1;

UART_HandleTypeDef huart1;
UART_HandleTypeDef huart2;

/* USER CODE BEGIN PV */

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART1_UART_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_I2C1_Init(void);
/* USER CODE BEGIN PFP */
typedef struct {
    float pressure_kpa;
    float temperature_c;
    float humidity_rh;
    uint8_t *rolldata;
} SensorData_t;

SensorData_t HIDS, PADS, PDUS;

void PADS_Init(I2C_HandleTypeDef *hi2c);
HAL_StatusTypeDef HIDS_Read(I2C_HandleTypeDef *hi2c, SensorData_t *data);
HAL_StatusTypeDef PADS_Read(I2C_HandleTypeDef *hi2c, SensorData_t *data);
HAL_StatusTypeDef PDUS_Read(I2C_HandleTypeDef *hi2c, SensorData_t *data);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
uint8_t Send_head[3]  = {0x02,0x00,0x3A};
uint8_t roll_data[18] = {0x02,0x00,0x0F};

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART1_UART_Init();
  MX_USART2_UART_Init();
  MX_I2C1_Init();
  /* USER CODE BEGIN 2 */

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  PADS_Init(&hi2c1);
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
	HIDS.rolldata = &roll_data[3];
	PADS.rolldata = &roll_data[9];
	PDUS.rolldata = &roll_data[14];
	HIDS_Read(&hi2c1, &HIDS);
	HAL_Delay(10);
	PADS_Read(&hi2c1, &PADS);
	HAL_Delay(10);
	PDUS_Read(&hi2c1, &PDUS);
	HAL_Delay(10);

	//allroll_read(&hi2c1);



	//uint8_t tt[] = "Hello word";
	HAL_UART_Transmit(&huart1, roll_data, sizeof(roll_data), 100);
	//uint8_t gg[6] = {0x02,0x00,0x3A,0x55,0x85,0x68};
	HAL_UART_Transmit(&huart2, roll_data, sizeof(roll_data), 100);
	HAL_Delay(10);
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_PeriphCLKInitTypeDef PeriphClkInit = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI|RCC_OSCILLATORTYPE_HSI48;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSI48State = RCC_HSI48_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI48;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_1) != HAL_OK)
  {
    Error_Handler();
  }
  PeriphClkInit.PeriphClockSelection = RCC_PERIPHCLK_USART1|RCC_PERIPHCLK_I2C1;
  PeriphClkInit.Usart1ClockSelection = RCC_USART1CLKSOURCE_PCLK1;
  PeriphClkInit.I2c1ClockSelection = RCC_I2C1CLKSOURCE_HSI;
  if (HAL_RCCEx_PeriphCLKConfig(&PeriphClkInit) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief I2C1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_I2C1_Init(void)
{

  /* USER CODE BEGIN I2C1_Init 0 */

  /* USER CODE END I2C1_Init 0 */

  /* USER CODE BEGIN I2C1_Init 1 */

  /* USER CODE END I2C1_Init 1 */
  hi2c1.Instance = I2C1;
  hi2c1.Init.Timing = 0x00401D2A;
  hi2c1.Init.OwnAddress1 = 0;
  hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
  hi2c1.Init.OwnAddress2 = 0;
  hi2c1.Init.OwnAddress2Masks = I2C_OA2_NOMASK;
  hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
  hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
  if (HAL_I2C_Init(&hi2c1) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Analogue filter
  */
  if (HAL_I2CEx_ConfigAnalogFilter(&hi2c1, I2C_ANALOGFILTER_ENABLE) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Digital filter
  */
  if (HAL_I2CEx_ConfigDigitalFilter(&hi2c1, 0) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN I2C1_Init 2 */

  /* USER CODE END I2C1_Init 2 */

}

/**
  * @brief USART1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART1_UART_Init(void)
{

  /* USER CODE BEGIN USART1_Init 0 */

  /* USER CODE END USART1_Init 0 */

  /* USER CODE BEGIN USART1_Init 1 */

  /* USER CODE END USART1_Init 1 */
  huart1.Instance = USART1;
  huart1.Init.BaudRate = 9600;
  huart1.Init.WordLength = UART_WORDLENGTH_8B;
  huart1.Init.StopBits = UART_STOPBITS_1;
  huart1.Init.Parity = UART_PARITY_NONE;
  huart1.Init.Mode = UART_MODE_TX_RX;
  huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart1.Init.OverSampling = UART_OVERSAMPLING_16;
  huart1.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
  huart1.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
  if (HAL_UART_Init(&huart1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART1_Init 2 */

  /* USER CODE END USART1_Init 2 */

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 9600;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  huart2.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
  huart2.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
/* USER CODE BEGIN MX_GPIO_Init_1 */
/* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

/* USER CODE BEGIN MX_GPIO_Init_2 */
/* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
#define HIDS_ADDR (0x44 <<1) //WSEN-HIDS (I²C 0x44) 讀取
#define PADS_ADDR (0x5C <<1) //WSEN-PADS (I²C 0x5C) 氣壓與溫度
#define PDUS_ADDR (0x78 <<1)


HAL_StatusTypeDef HIDS_Read(I2C_HandleTypeDef *hi2c, SensorData_t *data)
{
    uint8_t cmd = 0xFD;
    uint8_t rx[6];
    HAL_I2C_Master_Transmit(hi2c, HIDS_ADDR, &cmd, 1, HAL_MAX_DELAY);
    HAL_Delay(9); // wait conversion
    HAL_I2C_Master_Receive(hi2c, HIDS_ADDR, data->rolldata, 6, HAL_MAX_DELAY);

    uint16_t Traw = (data->rolldata[0] << 8) | data->rolldata[1];
    uint16_t RHraw = (data->rolldata[3] << 8) | data->rolldata[4];

    data->temperature_c = -45.0f + 175.0f * (float)Traw / 65535.0f;
    data->humidity_rh = 100.0f * (float)RHraw / 65535.0f;
    return HAL_OK;
}



void PADS_Init(I2C_HandleTypeDef *hi2c)
{
    uint8_t cfg[2] = {0x11, 0b00010010}; //
    HAL_I2C_Master_Transmit(hi2c, PADS_ADDR, cfg, 2, HAL_MAX_DELAY);
    uint8_t cfg2[2] = {0x10, 0b01001000}; //
    HAL_I2C_Master_Transmit(hi2c, PADS_ADDR, cfg2, 2, HAL_MAX_DELAY);
}

HAL_StatusTypeDef PADS_Read(I2C_HandleTypeDef *hi2c, SensorData_t *data)
{
    uint8_t reg = 0x28;
    uint8_t rx[5];
    HAL_I2C_Master_Transmit(hi2c, PADS_ADDR, &reg, 1, HAL_MAX_DELAY);
    HAL_Delay(10);
    HAL_I2C_Master_Receive(hi2c, PADS_ADDR, data->rolldata, 5, HAL_MAX_DELAY);

    int32_t Praw = ((int32_t)data->rolldata[2] << 16) | ((int32_t)data->rolldata[1] << 8) | data->rolldata[0];
    int16_t Traw = (int16_t)((data->rolldata[4] << 8) | data->rolldata[3]);
    data->pressure_kpa = (float)Praw / 40960.0f ; // convert Pa → kPa
    data->temperature_c = Traw * 0.01f;
    return HAL_OK;
}

//WSEN-PDUS (I²C 0x78) 差壓與溫度

#define OUTPMIN  3277
#define SENP     7.63e-5
#define PMIN     -1.0

HAL_StatusTypeDef PDUS_Read(I2C_HandleTypeDef *hi2c, SensorData_t *data)
{
    uint8_t rx[4];
    HAL_I2C_Master_Receive(hi2c, PDUS_ADDR, data->rolldata, 4, HAL_MAX_DELAY);

    uint16_t Praw = ((uint16_t)(data->rolldata[0] << 8) | data->rolldata[1]) & 0x7FFF;
    uint16_t Traw = ((uint16_t)(data->rolldata[2] << 8) | data->rolldata[3]) & 0x7FFF;

    data->pressure_kpa = (float)(Praw - OUTPMIN) * SENP + PMIN;
    data->temperature_c = (float)(Traw - 8192) * 4.272e-3f;
    return HAL_OK;
}

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
