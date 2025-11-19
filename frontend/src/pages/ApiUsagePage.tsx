/**
 * API Usage page - track OpenAI and Firecrawl API usage
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Button,
  Container,
  Heading,
  HStack,
  VStack,
  Text,
  useToast,
  Spinner,
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  Card,
  CardBody,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Badge,
  Divider,
  Select,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td
} from '@chakra-ui/react'
import { ChevronDownIcon } from '@chakra-ui/icons'
import { apiClient } from '../services/api'

interface ApiUsagePageProps {
  onLogout: () => void
}

export default function ApiUsagePage({ onLogout }: ApiUsagePageProps) {
  const [statistics, setStatistics] = useState<any>(null)
  const [history, setHistory] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [days, setDays] = useState(30)
  const [providerFilter, setProviderFilter] = useState<string>('')
  const navigate = useNavigate()
  const toast = useToast()

  useEffect(() => {
    loadData()
  }, [days, providerFilter])

  const loadData = async () => {
    setIsLoading(true)
    try {
      // Load statistics and history in parallel
      const [statsData, historyData] = await Promise.all([
        apiClient.getUsageStatistics(days),
        apiClient.getUsageHistory(days, providerFilter || undefined, 50)
      ])

      setStatistics(statsData)
      setHistory(historyData.records || [])
    } catch (error: any) {
      toast({
        title: 'Error loading API usage data',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 3000
      })
    } finally {
      setIsLoading(false)
    }
  }

  const formatCost = (cost: number) => {
    return `$${cost.toFixed(4)}`
  }

  const getSuccessRate = (successful: number, total: number) => {
    if (total === 0) return '0%'
    return `${((successful / total) * 100).toFixed(1)}%`
  }

  return (
    <Container maxW="container.xl" py={8}>
      <HStack justify="space-between" mb={6}>
        <Button variant="link" onClick={() => navigate('/')}>
          ← Back to Dashboard
        </Button>
        <Menu>
          <MenuButton as={Button} rightIcon={<ChevronDownIcon />}>
            Account
          </MenuButton>
          <MenuList>
            <MenuItem onClick={onLogout}>Logout</MenuItem>
          </MenuList>
        </Menu>
      </HStack>

      <VStack spacing={6} align="stretch">
        <Box>
          <Heading size="lg" mb={2}>API Usage Tracking</Heading>
          <Text color="gray.600">
            Monitor OpenAI Vision and Firecrawl API usage and costs
          </Text>
        </Box>

        {/* Time Period Selector */}
        <HStack>
          <Text fontWeight="semibold">Period:</Text>
          <Select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value))}
            maxW="200px"
          >
            <option value="7">Last 7 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
            <option value="365">Last year</option>
          </Select>
        </HStack>

        {isLoading ? (
          <Box textAlign="center" py={10}>
            <Spinner size="xl" />
          </Box>
        ) : !statistics ? (
          <Box textAlign="center" py={10}>
            <Text color="gray.500">No usage data available</Text>
          </Box>
        ) : (
          <>
            {/* Summary Cards */}
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
              {/* Total Cost */}
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Total Cost</StatLabel>
                    <StatNumber color="blue.500">
                      {formatCost(statistics.total_cost)}
                    </StatNumber>
                    <StatHelpText>Last {days} days</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>

              {/* OpenAI Stats */}
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>
                      <HStack>
                        <Text>OpenAI Vision</Text>
                        <Badge colorScheme="purple">Vision</Badge>
                      </HStack>
                    </StatLabel>
                    <StatNumber>
                      {statistics.openai.total_calls}
                      <Text as="span" fontSize="sm" color="gray.500" ml={2}>
                        calls
                      </Text>
                    </StatNumber>
                    <StatHelpText>
                      {formatCost(statistics.openai.total_cost)} •{' '}
                      {getSuccessRate(
                        statistics.openai.successful_calls,
                        statistics.openai.total_calls
                      )}{' '}
                      success
                    </StatHelpText>
                  </Stat>
                </CardBody>
              </Card>

              {/* Firecrawl Stats */}
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>
                      <HStack>
                        <Text>Firecrawl</Text>
                        <Badge colorScheme="orange">Scraping</Badge>
                      </HStack>
                    </StatLabel>
                    <StatNumber>
                      {statistics.firecrawl.total_calls}
                      <Text as="span" fontSize="sm" color="gray.500" ml={2}>
                        calls
                      </Text>
                    </StatNumber>
                    <StatHelpText>
                      {formatCost(statistics.firecrawl.total_cost)} •{' '}
                      {getSuccessRate(
                        statistics.firecrawl.successful_calls,
                        statistics.firecrawl.total_calls
                      )}{' '}
                      success
                    </StatHelpText>
                  </Stat>
                </CardBody>
              </Card>

              {/* Average Cost per Call */}
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Avg Cost / Call</StatLabel>
                    <StatNumber color="green.500">
                      {formatCost(
                        statistics.total_cost /
                          (statistics.openai.total_calls +
                            statistics.firecrawl.total_calls || 1)
                      )}
                    </StatNumber>
                    <StatHelpText>
                      {statistics.openai.total_calls +
                        statistics.firecrawl.total_calls}{' '}
                      total calls
                    </StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            <Divider />

            {/* Detailed Breakdown */}
            <Card>
              <CardBody>
                <VStack spacing={4} align="stretch">
                  <Heading size="md">Provider Breakdown</Heading>

                  <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                    {/* OpenAI Details */}
                    <Box>
                      <HStack mb={3}>
                        <Heading size="sm">OpenAI Vision API</Heading>
                        <Badge colorScheme="purple">Vision</Badge>
                      </HStack>
                      <VStack align="stretch" spacing={2} fontSize="sm">
                        <HStack justify="space-between">
                          <Text color="gray.600">Total Calls:</Text>
                          <Text fontWeight="semibold">
                            {statistics.openai.total_calls}
                          </Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text color="gray.600">Successful:</Text>
                          <Text color="green.500" fontWeight="semibold">
                            {statistics.openai.successful_calls}
                          </Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text color="gray.600">Failed:</Text>
                          <Text color="red.500" fontWeight="semibold">
                            {statistics.openai.failed_calls}
                          </Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text color="gray.600">Total Cost:</Text>
                          <Text fontWeight="bold" color="blue.500">
                            {formatCost(statistics.openai.total_cost)}
                          </Text>
                        </HStack>
                        {statistics.openai.total_tokens > 0 && (
                          <HStack justify="space-between">
                            <Text color="gray.600">Tokens Used:</Text>
                            <Text fontWeight="semibold">
                              {statistics.openai.total_tokens.toLocaleString()}
                            </Text>
                          </HStack>
                        )}
                      </VStack>
                    </Box>

                    {/* Firecrawl Details */}
                    <Box>
                      <HStack mb={3}>
                        <Heading size="sm">Firecrawl API</Heading>
                        <Badge colorScheme="orange">Scraping</Badge>
                      </HStack>
                      <VStack align="stretch" spacing={2} fontSize="sm">
                        <HStack justify="space-between">
                          <Text color="gray.600">Total Calls:</Text>
                          <Text fontWeight="semibold">
                            {statistics.firecrawl.total_calls}
                          </Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text color="gray.600">Successful:</Text>
                          <Text color="green.500" fontWeight="semibold">
                            {statistics.firecrawl.successful_calls}
                          </Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text color="gray.600">Failed:</Text>
                          <Text color="red.500" fontWeight="semibold">
                            {statistics.firecrawl.failed_calls}
                          </Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text color="gray.600">Total Cost:</Text>
                          <Text fontWeight="bold" color="blue.500">
                            {formatCost(statistics.firecrawl.total_cost)}
                          </Text>
                        </HStack>
                      </VStack>
                    </Box>
                  </SimpleGrid>
                </VStack>
              </CardBody>
            </Card>

            <Divider />

            {/* Recent Usage History */}
            <Box>
              <HStack justify="space-between" mb={4}>
                <Heading size="md">Recent API Calls</Heading>
                <Select
                  placeholder="All Providers"
                  value={providerFilter}
                  onChange={(e) => setProviderFilter(e.target.value)}
                  maxW="200px"
                  size="sm"
                >
                  <option value="openai">OpenAI only</option>
                  <option value="firecrawl">Firecrawl only</option>
                </Select>
              </HStack>

              {history.length === 0 ? (
                <Box textAlign="center" py={6}>
                  <Text color="gray.500">No API calls recorded</Text>
                </Box>
              ) : (
                <Box overflowX="auto">
                  <Table variant="simple" size="sm">
                    <Thead>
                      <Tr>
                        <Th>Provider</Th>
                        <Th>Operation</Th>
                        <Th>Status</Th>
                        <Th>Cost</Th>
                        <Th>Timestamp</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {history.map((record) => (
                        <Tr key={record.id}>
                          <Td>
                            <Badge
                              colorScheme={
                                record.provider === 'openai' ? 'purple' : 'orange'
                              }
                            >
                              {record.provider === 'openai'
                                ? 'OpenAI'
                                : 'Firecrawl'}
                            </Badge>
                          </Td>
                          <Td fontSize="xs">{record.operation}</Td>
                          <Td>
                            <Badge
                              colorScheme={record.success ? 'green' : 'red'}
                              fontSize="xs"
                            >
                              {record.success ? 'Success' : 'Failed'}
                            </Badge>
                          </Td>
                          <Td fontFamily="mono" fontSize="xs">
                            {formatCost(record.estimated_cost || 0)}
                          </Td>
                          <Td fontSize="xs" color="gray.600">
                            {new Date(record.created_at).toLocaleString()}
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </Box>
              )}
            </Box>

            {/* Cost Estimate Disclaimer */}
            <Box bg="blue.50" p={4} borderRadius="md">
              <Text fontSize="sm" color="gray.700">
                <strong>Note:</strong> Costs shown are estimates based on
                typical pricing. Actual costs may vary. OpenAI Vision:{' '}
                ~$0.003/image, Firecrawl: ~$0.005/scrape.
              </Text>
            </Box>
          </>
        )}
      </VStack>
    </Container>
  )
}
