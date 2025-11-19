/**
 * Dashboard page - lists all classification runs
 */
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Button,
  Container,
  Heading,
  HStack,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Progress,
  useToast,
  Spinner,
  Text,
  Menu,
  MenuButton,
  MenuList,
  MenuItem
} from '@chakra-ui/react'
import { ChevronDownIcon } from '@chakra-ui/icons'
import { apiClient } from '../services/api'
import type { Run } from '../types'
import { RunStatus } from '../types'

interface DashboardPageProps {
  onLogout: () => void
}

export default function DashboardPage({ onLogout }: DashboardPageProps) {
  const [runs, setRuns] = useState<Run[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()
  const toast = useToast()

  useEffect(() => {
    loadRuns()
    // Poll for updates every 5 seconds
    const interval = setInterval(loadRuns, 5000)
    return () => clearInterval(interval)
  }, [])

  const loadRuns = async () => {
    try {
      const response = await apiClient.listRuns(1, 50)
      setRuns(response.runs || [])
    } catch (error) {
      toast({
        title: 'Error loading runs',
        status: 'error',
        duration: 3000
      })
    } finally {
      setIsLoading(false)
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

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '-'
    return new Date(dateString).toLocaleString()
  }

  return (
    <Container maxW="container.xl" py={8}>
      <HStack justify="space-between" mb={6}>
        <Heading size="lg">Classification Runs</Heading>
        <HStack>
          <Button variant="outline" onClick={() => navigate('/api-usage')}>
            API Usage
          </Button>
          <Button colorScheme="blue" onClick={() => navigate('/runs/new')}>
            New Run
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
      </HStack>

      {isLoading ? (
        <Box textAlign="center" py={10}>
          <Spinner size="xl" />
        </Box>
      ) : runs.length === 0 ? (
        <Box textAlign="center" py={10}>
          <Text color="gray.500" mb={4}>No classification runs yet</Text>
          <Button colorScheme="blue" onClick={() => navigate('/runs/new')}>
            Create your first run
          </Button>
        </Box>
      ) : (
        <Table variant="simple">
          <Thead>
            <Tr>
              <Th>Name</Th>
              <Th>Status</Th>
              <Th>Progress</Th>
              <Th>Created</Th>
              <Th>Completed</Th>
              <Th>Actions</Th>
            </Tr>
          </Thead>
          <Tbody>
            {runs.map((run) => (
              <Tr key={run.id} _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
                <Td onClick={() => navigate(`/runs/${run.id}`)}>{run.name}</Td>
                <Td>
                  <Badge colorScheme={getStatusColor(run.status)}>
                    {run.status}
                  </Badge>
                </Td>
                <Td>
                  <Box>
                    <Text fontSize="sm" mb={1}>
                      {run.processed_records} / {run.total_records}
                    </Text>
                    <Progress
                      value={run.progress_percentage}
                      size="sm"
                      colorScheme="blue"
                      hasStripe
                      isAnimated={run.status === RunStatus.RUNNING}
                    />
                  </Box>
                </Td>
                <Td>{formatDate(run.created_at)}</Td>
                <Td>{formatDate(run.completed_at)}</Td>
                <Td>
                  <HStack>
                    <Button
                      size="sm"
                      onClick={() => navigate(`/runs/${run.id}`)}
                    >
                      View
                    </Button>
                    {run.status === RunStatus.COMPLETED && (
                      <Button
                        size="sm"
                        colorScheme="green"
                        onClick={() => navigate(`/runs/${run.id}/results`)}
                      >
                        Results
                      </Button>
                    )}
                  </HStack>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      )}
    </Container>
  )
}
