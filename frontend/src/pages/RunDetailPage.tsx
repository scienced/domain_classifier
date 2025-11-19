/**
 * Run Detail page - shows progress and statistics
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Box,
  Button,
  Container,
  Heading,
  HStack,
  VStack,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  Badge,
  useToast,
  Spinner,
  Text,
  Card,
  CardBody,
  Grid,
  GridItem,
  Menu,
  MenuButton,
  MenuList,
  MenuItem
} from '@chakra-ui/react'
import { ChevronDownIcon } from '@chakra-ui/icons'
import { apiClient } from '../services/api'
import { RunStatus } from '../types'

interface RunDetailPageProps {
  onLogout: () => void
}

export default function RunDetailPage({ onLogout }: RunDetailPageProps) {
  const { id } = useParams<{ id: string }>()
  const [run, setRun] = useState<any>(null)
  const [statistics, setStatistics] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()
  const toast = useToast()

  useEffect(() => {
    if (!id) return

    loadData()

    // Poll every 2 seconds while running
    const interval = setInterval(loadData, 2000)
    return () => clearInterval(interval)
  }, [id])

  const loadData = async () => {
    if (!id) return

    try {
      const [runStatus, stats] = await Promise.all([
        apiClient.getRunStatus(parseInt(id)),
        apiClient.getRunStatistics(parseInt(id))
      ])

      setRun(runStatus)
      setStatistics(stats)
    } catch (error) {
      toast({
        title: 'Error loading run details',
        status: 'error',
        duration: 3000
      })
    } finally {
      setIsLoading(false)
    }
  }

  const formatETA = (seconds: number | null) => {
    if (seconds === null || seconds === undefined) return 'Calculating...'

    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)

    if (hours > 0) {
      return `${hours}h ${minutes}m`
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`
    } else {
      return `${secs}s`
    }
  }

  const getStatusColor = (status: RunStatus) => {
    switch (status) {
      case RunStatus.COMPLETED:
        return 'green'
      case RunStatus.RUNNING:
        return 'blue'
      case RunStatus.PENDING:
        return 'yellow'
      case RunStatus.FAILED:
        return 'red'
      default:
        return 'gray'
    }
  }

  if (isLoading) {
    return (
      <Container maxW="container.xl" py={8}>
        <Box textAlign="center" py={10}>
          <Spinner size="xl" />
        </Box>
      </Container>
    )
  }

  if (!run) {
    return (
      <Container maxW="container.xl" py={8}>
        <Text>Run not found</Text>
      </Container>
    )
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
          <HStack justify="space-between" mb={2}>
            <Heading size="lg">{run.name}</Heading>
            <Badge colorScheme={getStatusColor(run.status)} fontSize="lg" px={3} py={1}>
              {run.status}
            </Badge>
          </HStack>
        </Box>

        {/* Progress Card */}
        <Card>
          <CardBody>
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <Text fontSize="lg" fontWeight="bold">Progress</Text>
                <Text fontSize="lg">
                  {run.processed_records} / {run.total_records} domains
                </Text>
              </HStack>
              <Progress
                value={run.progress_percentage}
                size="lg"
                colorScheme="blue"
                hasStripe
                isAnimated={run.status === RunStatus.RUNNING}
              />
              <HStack justify="space-between">
                <Text color="gray.600">{run.progress_percentage.toFixed(1)}% complete</Text>
                {run.status === RunStatus.RUNNING && (
                  <Text color="gray.600">ETA: {formatETA(run.eta_seconds)}</Text>
                )}
              </HStack>
            </VStack>
          </CardBody>
        </Card>

        {/* Statistics */}
        {statistics && (
          <>
            <Heading size="md">Statistics</Heading>

            <Grid templateColumns="repeat(3, 1fr)" gap={6}>
              <GridItem>
                <Card>
                  <CardBody>
                    <Stat>
                      <StatLabel>Completed</StatLabel>
                      <StatNumber>{statistics.completed_records}</StatNumber>
                    </Stat>
                  </CardBody>
                </Card>
              </GridItem>

              <GridItem>
                <Card>
                  <CardBody>
                    <Stat>
                      <StatLabel>Errors</StatLabel>
                      <StatNumber color={statistics.error_records > 0 ? 'red.500' : 'inherit'}>
                        {statistics.error_records}
                      </StatNumber>
                    </Stat>
                  </CardBody>
                </Card>
              </GridItem>

              <GridItem>
                <Card>
                  <CardBody>
                    <Stat>
                      <StatLabel>Avg Confidence</StatLabel>
                      <StatNumber>
                        {statistics.average_confidence
                          ? (statistics.average_confidence * 100).toFixed(1) + '%'
                          : 'N/A'}
                      </StatNumber>
                    </Stat>
                  </CardBody>
                </Card>
              </GridItem>
            </Grid>

            {/* Label Distribution */}
            {Object.keys(statistics.label_distribution).length > 0 && (
              <Card>
                <CardBody>
                  <Heading size="sm" mb={4}>Label Distribution</Heading>
                  <VStack spacing={2} align="stretch">
                    {Object.entries(statistics.label_distribution).map(([label, count]) => (
                      <HStack key={label} justify="space-between">
                        <Badge>{label}</Badge>
                        <Text>{count as number}</Text>
                      </HStack>
                    ))}
                  </VStack>
                </CardBody>
              </Card>
            )}

            {/* Stage Distribution */}
            {Object.keys(statistics.stage_distribution).length > 0 && (
              <Card>
                <CardBody>
                  <Heading size="sm" mb={4}>Stage Distribution</Heading>
                  <VStack spacing={2} align="stretch">
                    {Object.entries(statistics.stage_distribution).map(([stage, count]) => (
                      <HStack key={stage} justify="space-between">
                        <Badge>{stage}</Badge>
                        <Text>{count as number}</Text>
                      </HStack>
                    ))}
                  </VStack>
                </CardBody>
              </Card>
            )}
          </>
        )}

        {/* Actions */}
        <HStack>
          {run.status === RunStatus.COMPLETED && (
            <Button
              colorScheme="green"
              onClick={() => navigate(`/runs/${id}/results`)}
            >
              View Results
            </Button>
          )}
        </HStack>
      </VStack>
    </Container>
  )
}
