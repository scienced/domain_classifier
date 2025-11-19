/**
 * New Run page - create and upload domains
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Button,
  Container,
  FormControl,
  FormLabel,
  Heading,
  Input,
  VStack,
  Text,
  useToast,
  Card,
  CardBody,
  HStack,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Textarea,
  Select,
  Switch,
  Badge,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Divider
} from '@chakra-ui/react'
import { ChevronDownIcon, CheckCircleIcon } from '@chakra-ui/icons'
import { apiClient } from '../services/api'

interface NewRunPageProps {
  onLogout: () => void
}

export default function NewRunPage({ onLogout }: NewRunPageProps) {
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [manualDomains, setManualDomains] = useState('')
  const [csvPreview, setCsvPreview] = useState<string[]>([])
  const [csvValid, setCsvValid] = useState(false)
  const [csvError, setCsvError] = useState('')
  const [industry, setIndustry] = useState('bodywear')
  const [detectBrandRetailer, setDetectBrandRetailer] = useState(false)
  const [uploadMethod, setUploadMethod] = useState<'csv' | 'manual'>('csv')
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()
  const toast = useToast()

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0] || null
    setFile(selectedFile)
    setCsvPreview([])
    setCsvValid(false)
    setCsvError('')

    if (!selectedFile) return

    try {
      const text = await selectedFile.text()
      const lines = text.split('\n').filter(line => line.trim())

      if (lines.length === 0) {
        setCsvError('CSV file is empty')
        return
      }

      // Check for header
      const header = lines[0].toLowerCase()
      if (!header.includes('domain')) {
        setCsvError('CSV must contain a "domain" column header')
        return
      }

      // Parse domains (skip header)
      const domains = lines.slice(1)
        .map(line => {
          // Simple CSV parsing - get first column
          const parts = line.split(',')
          return parts[0].trim()
        })
        .filter(domain => domain && domain !== 'domain')

      if (domains.length === 0) {
        setCsvError('No valid domains found in CSV')
        return
      }

      setCsvPreview(domains.slice(0, 10)) // Show first 10
      setCsvValid(true)
    } catch (error) {
      setCsvError('Error reading CSV file')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!name.trim()) {
      toast({
        title: 'Please enter a run name',
        status: 'warning',
        duration: 3000
      })
      return
    }

    // Validate domains based on upload method
    let domains: string[] = []

    if (uploadMethod === 'csv') {
      if (!file || !csvValid) {
        toast({
          title: 'Please upload a valid CSV file',
          status: 'warning',
          duration: 3000
        })
        return
      }
    } else {
      // Manual entry
      if (!manualDomains.trim()) {
        toast({
          title: 'Please enter at least one domain',
          status: 'warning',
          duration: 3000
        })
        return
      }

      domains = manualDomains
        .split('\n')
        .map(d => d.trim())
        .filter(d => d && !d.startsWith('#'))
    }

    setIsLoading(true)

    try {
      // Create run
      const run = await apiClient.createRun(name)

      // Upload domains
      if (uploadMethod === 'csv' && file) {
        await apiClient.uploadCSV(run.id, file)
      } else {
        await apiClient.uploadDomains(run.id, domains)
      }

      // Start run
      await apiClient.startRun(run.id)

      toast({
        title: 'Run created successfully',
        description: 'Processing has started',
        status: 'success',
        duration: 3000
      })

      navigate(`/runs/${run.id}`)
    } catch (error: any) {
      toast({
        title: 'Error creating run',
        description: error.response?.data?.detail || error.message,
        status: 'error',
        duration: 5000
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Container maxW="container.lg" py={8}>
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

      <Card>
        <CardBody>
          <VStack spacing={6} align="stretch">
            <Box>
              <Heading size="lg" mb={2}>Create New Classification Run</Heading>
              <Text color="gray.600">
                Configure and start a new brand classification run
              </Text>
            </Box>

            <form onSubmit={handleSubmit}>
              <VStack spacing={6} align="stretch">
                {/* Run Name */}
                <FormControl isRequired>
                  <FormLabel>Run Name</FormLabel>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., Q1 2024 Bodywear Analysis"
                  />
                </FormControl>

                <Divider />

                {/* Industry Selection */}
                <FormControl>
                  <FormLabel>
                    Sub-Industry Classification
                    <Badge ml={2} colorScheme="blue">Active</Badge>
                  </FormLabel>
                  <Select value={industry} onChange={(e) => setIndustry(e.target.value)}>
                    <option value="bodywear">Bodywear (Lingerie, Swimwear, Sleepwear)</option>
                    <option value="kidswear" disabled>Kidswear (Coming Soon)</option>
                    <option value="footwear" disabled>Footwear (Coming Soon)</option>
                    <option value="accessories" disabled>Accessories (Coming Soon)</option>
                    <option value="sportswear" disabled>Sportswear (Coming Soon)</option>
                  </Select>
                  <Text fontSize="sm" color="gray.500" mt={2}>
                    Select which fashion sub-industry to classify for
                  </Text>
                </FormControl>

                {/* Brand vs Retailer Detection */}
                <FormControl display="flex" alignItems="center">
                  <FormLabel mb="0" flex="1">
                    Brand vs Retailer Detection
                    <Badge ml={2} colorScheme="gray">Coming Soon</Badge>
                  </FormLabel>
                  <Switch
                    isChecked={detectBrandRetailer}
                    onChange={(e) => setDetectBrandRetailer(e.target.checked)}
                    isDisabled={true}
                  />
                </FormControl>
                <Text fontSize="sm" color="gray.500" mt={-4}>
                  Automatically detect whether a website is a brand or a retailer
                </Text>

                <Divider />

                {/* Domain Upload */}
                <Box>
                  <FormLabel>Domain Upload Method</FormLabel>
                  <Tabs
                    variant="enclosed"
                    onChange={(index) => setUploadMethod(index === 0 ? 'csv' : 'manual')}
                  >
                    <TabList>
                      <Tab>Upload CSV File</Tab>
                      <Tab>Manual Entry</Tab>
                    </TabList>

                    <TabPanels>
                      {/* CSV Upload Tab */}
                      <TabPanel>
                        <VStack spacing={4} align="stretch">
                          <FormControl isRequired={uploadMethod === 'csv'}>
                            <FormLabel>CSV File</FormLabel>
                            <Input
                              type="file"
                              accept=".csv"
                              onChange={handleFileChange}
                              pt={1}
                            />
                            <Text fontSize="sm" color="gray.500" mt={2}>
                              CSV must contain a 'domain' column with website domains
                            </Text>
                          </FormControl>

                          {/* CSV Validation Messages */}
                          {csvValid && (
                            <Alert status="success" borderRadius="md">
                              <AlertIcon as={CheckCircleIcon} />
                              <Box>
                                <AlertTitle>CSV Valid!</AlertTitle>
                                <AlertDescription>
                                  Found {csvPreview.length > 0 && file ?
                                    `${(file as File).size > 0 ? csvPreview.length + '+' : csvPreview.length} domains` :
                                    'valid domains'} with correct header format
                                </AlertDescription>
                              </Box>
                            </Alert>
                          )}

                          {csvError && (
                            <Alert status="error" borderRadius="md">
                              <AlertIcon />
                              <AlertDescription>{csvError}</AlertDescription>
                            </Alert>
                          )}

                          {/* CSV Preview */}
                          {csvPreview.length > 0 && (
                            <Box>
                              <Text fontWeight="bold" mb={2}>Preview (first 10 domains):</Text>
                              <Box
                                borderWidth="1px"
                                borderRadius="md"
                                overflow="hidden"
                                maxH="300px"
                                overflowY="auto"
                              >
                                <Table size="sm">
                                  <Thead bg="gray.50">
                                    <Tr>
                                      <Th>#</Th>
                                      <Th>Domain</Th>
                                    </Tr>
                                  </Thead>
                                  <Tbody>
                                    {csvPreview.map((domain, index) => (
                                      <Tr key={index}>
                                        <Td>{index + 1}</Td>
                                        <Td fontFamily="mono" fontSize="sm">{domain}</Td>
                                      </Tr>
                                    ))}
                                  </Tbody>
                                </Table>
                              </Box>
                            </Box>
                          )}

                          {/* Format Example */}
                          <Box bg="blue.50" p={4} borderRadius="md">
                            <Text fontSize="sm" fontWeight="bold" mb={2}>
                              CSV Format Example:
                            </Text>
                            <Text fontSize="sm" fontFamily="mono">
                              domain<br />
                              example.com<br />
                              another-site.com<br />
                              brand-website.com
                            </Text>
                          </Box>
                        </VStack>
                      </TabPanel>

                      {/* Manual Entry Tab */}
                      <TabPanel>
                        <VStack spacing={4} align="stretch">
                          <FormControl isRequired={uploadMethod === 'manual'}>
                            <FormLabel>Domain List</FormLabel>
                            <Textarea
                              value={manualDomains}
                              onChange={(e) => setManualDomains(e.target.value)}
                              placeholder="example.com&#10;another-site.com&#10;brand-website.com"
                              rows={10}
                              fontFamily="mono"
                              fontSize="sm"
                            />
                            <Text fontSize="sm" color="gray.500" mt={2}>
                              Enter one domain per line. Lines starting with # are ignored.
                            </Text>
                          </FormControl>

                          {manualDomains && (
                            <Alert status="info" borderRadius="md">
                              <AlertIcon />
                              <AlertDescription>
                                {manualDomains.split('\n').filter(d => d.trim() && !d.startsWith('#')).length} domains ready to process
                              </AlertDescription>
                            </Alert>
                          )}

                          <Box bg="blue.50" p={4} borderRadius="md">
                            <Text fontSize="sm" fontWeight="bold" mb={2}>
                              Tips:
                            </Text>
                            <Text fontSize="sm">
                              • One domain per line<br />
                              • No need for http:// or https://<br />
                              • Lines starting with # are treated as comments<br />
                              • Empty lines are ignored
                            </Text>
                          </Box>
                        </VStack>
                      </TabPanel>
                    </TabPanels>
                  </Tabs>
                </Box>

                {/* Action Buttons */}
                <HStack width="100%" justify="flex-end" pt={4}>
                  <Button onClick={() => navigate('/')}>
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    colorScheme="blue"
                    isLoading={isLoading}
                  >
                    Create and Start Run
                  </Button>
                </HStack>
              </VStack>
            </form>
          </VStack>
        </CardBody>
      </Card>
    </Container>
  )
}
