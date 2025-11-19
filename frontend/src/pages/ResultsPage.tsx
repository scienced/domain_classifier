/**
 * Results page - view and edit classification results
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
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
  Select,
  Input,
  useToast,
  Spinner,
  Text,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Textarea,
  useDisclosure,
  VStack
} from '@chakra-ui/react'
import { ChevronDownIcon, DownloadIcon } from '@chakra-ui/icons'
import { apiClient } from '../services/api'
import type { ClassificationRecord } from '../types'
import { Label, RecordStatus } from '../types'

interface ResultsPageProps {
  onLogout: () => void
}

export default function ResultsPage({ onLogout }: ResultsPageProps) {
  const { id } = useParams<{ id: string }>()
  const [records, setRecords] = useState<ClassificationRecord[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [labelFilter, setLabelFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedRecord, setSelectedRecord] = useState<ClassificationRecord | null>(null)
  const { isOpen, onOpen, onClose } = useDisclosure()
  const [newLabel, setNewLabel] = useState('')
  const [userNote, setUserNote] = useState('')
  const navigate = useNavigate()
  const toast = useToast()

  const pageSize = 50

  useEffect(() => {
    if (!id) return
    loadRecords()
  }, [id, page, labelFilter, statusFilter])

  const loadRecords = async () => {
    if (!id) return

    setIsLoading(true)
    try {
      const filters: any = {}
      if (labelFilter) filters.label = labelFilter
      if (statusFilter) filters.status = statusFilter

      const response = await apiClient.listRecords(
        parseInt(id),
        page,
        pageSize,
        filters
      )

      setRecords(response.records || [])
      setTotal(response.total)
    } catch (error) {
      toast({
        title: 'Error loading results',
        status: 'error',
        duration: 3000
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleExport = async () => {
    if (!id) return

    try {
      const blob = await apiClient.exportCSV(parseInt(id))
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `run_${id}_results.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      toast({
        title: 'CSV exported successfully',
        status: 'success',
        duration: 3000
      })
    } catch (error) {
      toast({
        title: 'Error exporting CSV',
        status: 'error',
        duration: 3000
      })
    }
  }

  const handleOverride = (record: ClassificationRecord) => {
    setSelectedRecord(record)
    setNewLabel(record.label || Label.NEEDS_REVIEW)
    setUserNote('')
    onOpen()
  }

  const submitOverride = async () => {
    if (!selectedRecord) return

    try {
      await apiClient.createOverride(selectedRecord.id, newLabel, userNote)

      toast({
        title: 'Override saved',
        status: 'success',
        duration: 3000
      })

      onClose()
      loadRecords()
    } catch (error) {
      toast({
        title: 'Error saving override',
        status: 'error',
        duration: 3000
      })
    }
  }

  const getLabelColor = (label: Label | null) => {
    if (!label) return 'gray'
    switch (label) {
      case Label.PURE_BODYWEAR:
        return 'green'
      case Label.BODYWEAR_LEANING:
        return 'blue'
      case Label.NEEDS_REVIEW:
        return 'yellow'
      case Label.GENERALIST:
        return 'orange'
      case Label.ERROR:
        return 'red'
      default:
        return 'gray'
    }
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <Container maxW="container.xl" py={8}>
      <HStack justify="space-between" mb={6}>
        <Button variant="link" onClick={() => navigate('/')}>
          ← Back to Dashboard
        </Button>
        <HStack>
          <Button leftIcon={<DownloadIcon />} onClick={handleExport}>
            Export CSV
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

      <Heading size="lg" mb={6}>Classification Results</Heading>

      {/* Filters */}
      <HStack mb={4} spacing={4}>
        <Select
          placeholder="All Labels"
          value={labelFilter}
          onChange={(e) => {
            setLabelFilter(e.target.value)
            setPage(1)
          }}
          maxW="250px"
        >
          {Object.values(Label).map((label) => (
            <option key={label} value={label}>{label}</option>
          ))}
        </Select>

        <Select
          placeholder="All Statuses"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value)
            setPage(1)
          }}
          maxW="250px"
        >
          {Object.values(RecordStatus).map((status) => (
            <option key={status} value={status}>{status}</option>
          ))}
        </Select>

        <Button onClick={() => {
          setLabelFilter('')
          setStatusFilter('')
          setPage(1)
        }}>
          Clear Filters
        </Button>
      </HStack>

      {isLoading ? (
        <Box textAlign="center" py={10}>
          <Spinner size="xl" />
        </Box>
      ) : records.length === 0 ? (
        <Box textAlign="center" py={10}>
          <Text color="gray.500">No results found</Text>
        </Box>
      ) : (
        <>
          <Box overflowX="auto">
            <Table variant="simple" size="sm">
              <Thead>
                <Tr>
                  <Th>Domain</Th>
                  <Th>Label</Th>
                  <Th>Confidence</Th>
                  <Th>Stage</Th>
                  <Th>Status</Th>
                  <Th>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {records.map((record) => (
                  <Tr key={record.id} bg={record.is_overridden ? 'yellow.50' : 'inherit'}>
                    <Td>
                      <Text fontFamily="mono" fontSize="sm">{record.domain}</Text>
                      {record.error && (
                        <Text fontSize="xs" color="red.500" mt={1}>
                          Error: {record.error.substring(0, 100)}
                        </Text>
                      )}
                    </Td>
                    <Td>
                      {record.label && (
                        <Badge colorScheme={getLabelColor(record.label)}>
                          {record.label}
                        </Badge>
                      )}
                      {record.is_overridden && (
                        <Badge ml={2} colorScheme="purple" fontSize="xs">
                          OVERRIDDEN
                        </Badge>
                      )}
                    </Td>
                    <Td>
                      {record.confidence !== null
                        ? (record.confidence * 100).toFixed(1) + '%'
                        : '-'}
                    </Td>
                    <Td>
                      <Text fontSize="sm">{record.stage_used || '-'}</Text>
                    </Td>
                    <Td>
                      <Badge
                        colorScheme={
                          record.status === RecordStatus.COMPLETED ? 'green' :
                          record.status === RecordStatus.ERROR ? 'red' :
                          record.status === RecordStatus.PROCESSING ? 'blue' : 'gray'
                        }
                        fontSize="xs"
                      >
                        {record.status}
                      </Badge>
                    </Td>
                    <Td>
                      {record.status === RecordStatus.COMPLETED && (
                        <Button size="xs" onClick={() => handleOverride(record)}>
                          Override
                        </Button>
                      )}
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>

          {/* Pagination */}
          <HStack justify="space-between" mt={4}>
            <Text>
              Showing {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, total)} of {total}
            </Text>
            <HStack>
              <Button
                size="sm"
                isDisabled={page === 1}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </Button>
              <Text>Page {page} of {totalPages}</Text>
              <Button
                size="sm"
                isDisabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
              >
                Next
              </Button>
            </HStack>
          </HStack>
        </>
      )}

      {/* Override Modal */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Override Classification</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Domain</FormLabel>
                <Input value={selectedRecord?.domain || ''} isReadOnly />
              </FormControl>

              <FormControl>
                <FormLabel>Current Label</FormLabel>
                <Input value={selectedRecord?.label || ''} isReadOnly />
              </FormControl>

              <FormControl isRequired>
                <FormLabel>New Label</FormLabel>
                <Select value={newLabel} onChange={(e) => setNewLabel(e.target.value)}>
                  {Object.values(Label).filter(l => l !== Label.ERROR).map((label) => (
                    <option key={label} value={label}>{label}</option>
                  ))}
                </Select>
              </FormControl>

              <FormControl>
                <FormLabel>Note (optional)</FormLabel>
                <Textarea
                  value={userNote}
                  onChange={(e) => setUserNote(e.target.value)}
                  placeholder="Add a note explaining the override..."
                />
              </FormControl>
            </VStack>
          </ModalBody>

          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Cancel
            </Button>
            <Button colorScheme="blue" onClick={submitOverride}>
              Save Override
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Container>
  )
}
